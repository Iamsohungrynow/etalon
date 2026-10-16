"""Compare Meep and etalon results → bench/results/<sha>.md and <sha>.json ("meep_comparison").

    python -m bench.report                # every tier in config.yaml
    python -m bench.report --tier 2d

Reads bench/meep/out/<tier>/<device>.json and bench/etalon/out/<tier>/<device>.json.
Results are compared only when both were made from the current config.yaml (same config
hash), on the same wavelengths and ports. Gates are those of plan §8 (bench/metrics.py).
"""

import argparse
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from bench import metrics
from bench.config import BenchConfig, load_config
from bench.record import RESULTS, git_sha, update_record
from bench.schema import (
    BENCH,
    DeviceResult,
    RunRecord,
    decode_complex,
    now_utc,
    out_path,
    read_result,
)

COMPARED = {
    "point2d": "T21 = Hz(probe 2) / Hz(probe 1), complex",
    "straight": "|S21| and phase (as Δn_eff)",
    "bend": "|S21|",
    "dc": "|S31|², |S41|² (coupling ratio)",
    "mmi": "|S21|², |S31|², imbalance",
    "ring": "λ_res, FSR, Q, through-port minimum (extinction)",
}


@dataclass
class Row:
    """One device in one tier."""

    device: str
    tier: str
    status: str
    """"compared", or why not: "needs M1 ...", "no Meep result", "stale Meep result", ..."""
    resolution: int
    meep: DeviceResult | None = None
    etalon: DeviceResult | None = None
    comparison: metrics.Comparison | None = None
    """Against the CUDA run if it ran, else the NumPy run."""
    compared_backend: str | None = None
    numpy_comparison: metrics.Comparison | None = None
    cuda_vs_numpy: float | None = None
    """max |S_cuda − S_numpy| over every entry: CLAUDE.md's identical-result CPU fallback."""
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool | None:
        if self.comparison is None:
            return None
        gated = [m.passed for m in self.comparison.metrics if m.gate is not None]
        return all(gated) if gated else None


def build_rows(cfg: BenchConfig, tier_name: str, root: Path = BENCH) -> list[Row]:
    """Load, check and compare every device of ``tier_name``."""
    tier = cfg.tier(tier_name)
    rows = []
    for device in tier.devices:
        row = Row(device, tier_name, "compared", tier.resolution)
        expected = cfg.config_sha256(tier_name, device)
        for solver in ("meep", "etalon"):
            path = out_path(solver, tier_name, device, root)
            if not path.exists():
                continue
            result = read_result(path)
            if result.config_sha256 != expected:
                row.notes.append(
                    f"stale {solver} result: made from a different config.yaml; re-run it"
                )
                continue
            setattr(row, solver, result)
        rows.append(row)
        if row.meep is not None:
            row.notes.extend(meep_sanity(device, row.meep))
        converged = _decay_notes(row)
        if row.meep is None:
            row.status = "no Meep result"
            continue
        if row.etalon is None:
            row.status = "no etalon result"
            continue
        if not _same_axes(row.meep, row.etalon):
            row.status = "mismatch: wavelengths or ports differ"
            continue
        runs = {run.backend: run for run in row.etalon.runs}
        unsupported = [r for r in runs.values() if r.status == "unsupported"]
        if unsupported:
            row.status = unsupported[0].message or "unsupported"
            continue
        meep_s = _spectra(row.meep.runs[0])
        length = _port_spacing(row.meep) if device == "straight" else None
        wl = np.asarray(row.meep.wavelengths_um)
        ok: dict[str, RunRecord] = {b: r for b, r in runs.items() if r.status == "ok" and r.s}
        if not ok:
            row.status = "no etalon run with S-parameters"
            continue
        backend = "cuda" if "cuda" in ok else "numpy"
        row.compared_backend = backend
        row.comparison = metrics.compare(device, wl, meep_s, _spectra(ok[backend]), length)
        if backend == "cuda" and "numpy" in ok:
            row.numpy_comparison = metrics.compare(
                device, wl, meep_s, _spectra(ok["numpy"]), length
            )
            cu, npy = _spectra(ok["cuda"]), _spectra(ok["numpy"])
            row.cuda_vs_numpy = max(float(np.max(np.abs(cu[k] - npy[k]))) for k in cu)
        if not converged:
            row.status = "not converged"
    return rows


def _decay_notes(row: Row) -> bool:
    """Note every run whose output-port fields did not decay; False if any did not."""
    converged = True
    for solver, result in (("Meep", row.meep), ("etalon", row.etalon)):
        for run in result.runs if result is not None else []:
            if run.final_decay is not None and run.final_decay > metrics.DECAY_LIMIT:
                converged = False
                row.notes.append(
                    f"{solver} {run.backend} not converged: fields at the output ports decayed "
                    f"only to {run.final_decay:.1e} of peak (limit {metrics.DECAY_LIMIT:.0e}); "
                    "increase run_time_fs"
                )
    return converged


def meep_sanity(device: str, result: DeviceResult) -> list[str]:
    """Checks on the Meep reference itself, so a broken reference cannot pass quietly."""
    run = result.runs[0]
    if run.status != "ok" or not run.s:
        return []
    s = _spectra(run)
    flags = []
    if device == "straight" and np.min(np.abs(s["S21"])) < 0.99:
        flags.append(f"Meep sanity: straight |S21| min {np.min(np.abs(s['S21'])):.4f} < 0.99")
    if device != "point2d":
        total = sum(metrics.power(v) for v in s.values())
        if np.max(total) > 1.001:
            flags.append(f"Meep sanity: Σ|S_i1|² reaches {np.max(total):.4f} > 1.001")
        if "S11" in s and np.max(np.abs(s["S11"])) > 0.05:
            flags.append(f"Meep sanity: |S11| reaches {np.max(np.abs(s['S11'])):.3f} > 0.05")
    if device == "mmi":
        asym = np.max(np.abs(np.abs(s["S21"]) - np.abs(s["S31"])))
        if asym > 1e-3:
            flags.append(
                f"Meep sanity: MMI | |S21| − |S31| | reaches {asym:.1e} (symmetric device)"
            )
    return flags


def _spectra(run: RunRecord) -> dict[str, np.ndarray]:
    return {key: decode_complex(values) for key, values in run.s.items()}


def _same_axes(a: DeviceResult, b: DeviceResult) -> bool:
    same_wl = len(a.wavelengths_um) == len(b.wavelengths_um) and np.allclose(
        a.wavelengths_um, b.wavelengths_um, rtol=0, atol=1e-12
    )
    return same_wl and a.ports == b.ports


def _port_spacing(result: DeviceResult) -> float:
    p1, p2 = (np.asarray(p.center_um) for p in result.ports[:2])
    return float(np.linalg.norm(p2 - p1))


# ---------------------------------------------------------------- formatting


def cell(text: str) -> str:
    """Escape the pipes in |S21| and friends so they do not split a markdown table cell."""
    return text.replace("|", r"\|")


def fmt_time(seconds: float | None, estimated: bool = False) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "—"
    if seconds < 120:
        text = f"{seconds:.1f} s"
    elif seconds < 7200:
        text = f"{seconds / 60:.1f} min"
    else:
        text = f"{seconds / 3600:.1f} h"
    return f"est. {text}" if estimated else text


def fmt_value(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "—"
    return (
        f"{value:.2e}"
        if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e4)
        else f"{value:.4f}"
    )


def _run(result: DeviceResult | None, backend: str) -> RunRecord | None:
    return result.run(backend) if result is not None else None


def _timing(run: RunRecord | None) -> str:
    if run is None:
        return "—"
    if run.status != "ok":
        return run.status
    return fmt_time(run.wall_time_s, run.extrapolated)


def render_markdown(cfg: BenchConfig, tables: dict[str, list[Row]], sha: str) -> str:
    lines = [f"# etalon vs Meep — {sha}", "", f"Generated {now_utc()} by `python -m bench.report`."]
    lines += ["Plan and gates: `docs/plan-bench.md` §8; numbers: `bench/config.yaml`.", ""]
    meep_run = next((r.meep.runs[0] for rows in tables.values() for r in rows if r.meep), None)
    etalon_runs = [
        run for rows in tables.values() for r in rows if r.etalon for run in r.etalon.runs
    ]
    if meep_run is not None:
        hw = meep_run.hardware
        lines.append(
            f"- **Meep** {meep_run.versions.get('meep', '?')}, {hw.get('processes')} MPI ranks, "
            f"double precision, on {hw.get('cpu')} ({hw.get('platform')})"
        )
    gpus = [
        r.hardware.get("device") for r in etalon_runs if r.backend == "cuda" and r.status == "ok"
    ]
    gpu = gpus[0] if gpus else None
    version = next((r.versions.get("etalon") for r in etalon_runs), None)
    if version:
        lines.append(
            f"- **etalon** {version}, {cfg.etalon.precision} precision; GPU: {gpu or '—'}; "
            "CPU: NumPy reference backend, one thread"
        )
    lines.append("")
    for tier_name, rows in tables.items():
        tier = cfg.tier(tier_name)
        lines += [
            f"## Tier {tier_name}: {tier.dims}D, resolution {tier.resolution} px/µm "
            f"(Δ = {tier.dl * 1e3:.0f} nm), PML {tier.pml} µm, Meep S = {tier.courant_meep} "
            f"(etalon courant {tier.courant_etalon:.4f})",
            "",
        ]
        if tier.core_index is not None:
            n_clad = cfg.materials.sio2
            lines += [
                f"2D effective-index model: core n = {tier.core_index}, cladding {n_clad}.",
                "",
            ]
        lines += [
            "| Device | Compared | Gate | Max Δ | Pass | Max \\|ΔS\\| "
            "| etalon GPU | etalon CPU | Meep CPU | Resolution |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            gpu_run, cpu_run = _run(row.etalon, "cuda"), _run(row.etalon, "numpy")
            meep_time = _timing(row.meep.runs[0]) if row.meep else "—"
            if row.comparison is None:
                lines.append(
                    f"| {row.device} | {cell(row.status)} | — | — | — | — | {_timing(gpu_run)} | "
                    f"{_timing(cpu_run)} | {meep_time} | {row.resolution} |"
                )
                continue
            gated = [m for m in row.comparison.metrics if m.gate is not None]
            worst = (
                max(gated, key=lambda m: (m.value or math.inf) / (m.gate or 1)) if gated else None
            )
            verdict = {True: "✓", False: "✗", None: "—"}[row.passed]
            if row.status != "compared":
                verdict = f"— ({cell(row.status)})"
            gate = fmt_value(worst.gate) if worst else "—"
            value = fmt_value(worst.value) if worst else "—"
            lines.append(
                f"| {row.device} | {cell(COMPARED[row.device])} | {gate} | {value} | {verdict} | "
                f"{fmt_value(row.comparison.max_abs_s)} | {_timing(gpu_run)} | "
                f"{_timing(cpu_run)} | {meep_time} | {row.resolution} |"
            )
        lines.append("")
        for row in rows:
            lines += _details(row)
    return "\n".join(lines).rstrip() + "\n"


def _details(row: Row) -> list[str]:
    out = [f"### {row.tier} · {row.device}", ""]
    if row.comparison is not None:
        out += ["| Metric | Value | Gate | Pass |", "| --- | --- | --- | --- |"]
        for m in row.comparison.metrics:
            unit = f" {m.unit}" if m.unit else ""
            verdict = {True: "✓", False: "✗", None: ""}[m.passed]
            gate = fmt_value(m.gate) if m.gate else ""
            out.append(f"| {cell(m.name)} | {fmt_value(m.value)}{unit} | {gate} | {verdict} |")
        out.append("")
        out.append(f"Compared against etalon's {row.compared_backend} run.")
        if row.numpy_comparison is not None:
            worst = max(
                (m.value or 0.0) for m in row.numpy_comparison.metrics if m.gate is not None
            )
            out.append(f"NumPy run vs Meep: worst gated metric {fmt_value(worst)}.")
        if row.cuda_vs_numpy is not None:
            out.append(f"CUDA vs NumPy: max |ΔS| = {fmt_value(row.cuda_vs_numpy)}.")
        out.append("")
        if row.device == "ring":
            out += _ring_table(row.comparison)
    elif row.meep is not None and row.meep.runs[0].s:
        out += _meep_summary(row)
    for result in (row.meep, row.etalon):
        if result is None:
            continue
        for run in result.runs:
            if run.status == "ok" and run.grid is not None:
                rate = (
                    run.grid.cells_total * run.grid.steps / run.stepping_time_s
                    if run.stepping_time_s
                    else None
                )
                out.append(
                    f"- {result.solver} {run.backend}: {run.grid.cells_total:.3g} cells "
                    f"({' × '.join(map(str, run.grid.cells))}), {run.grid.steps} steps, "
                    f"wall {fmt_time(run.wall_time_s, run.extrapolated)}, stepping "
                    f"{fmt_time(run.stepping_time_s, run.extrapolated)}"
                    + (f", {rate:.2e} cell-updates/s" if rate else "")
                    + (
                        f", final decay {run.final_decay:.1e}"
                        if run.final_decay is not None
                        else ""
                    )
                )
    out += [f"- {note}" for note in row.notes]
    out.append("")
    return out


def _ring_table(comparison: metrics.Comparison) -> list[str]:
    out = [
        "| | λ_res (µm) | Q | through min | extinction (dB) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for solver in ("meep", "etalon"):
        resonances = comparison.details.get(solver, [])
        assert isinstance(resonances, list)
        for r in resonances:
            er = r.extinction_db
            out.append(f"| {solver} | {r.wavelength:.5f} | {r.q:.0f} | {r.t_min:.4f} | {er:.2f} |")
    out.append("")
    return out


def _meep_summary(row: Row) -> list[str]:
    """Meep reference values for a device etalon cannot run yet."""
    assert row.meep is not None
    s = _spectra(row.meep.runs[0])
    wl = np.asarray(row.meep.wavelengths_um)
    mid = int(np.argmin(np.abs(wl - wl.mean())))
    parts = [f"|{k}|² = {metrics.power(v)[mid]:.4f}" for k, v in sorted(s.items())]
    out = [f"Meep reference at λ = {wl[mid]:.4f} µm: " + ", ".join(parts) + "."]
    if row.device == "ring":
        res = metrics.find_resonances(wl, metrics.power(s["S31"]), metrics.power(s["S21"]))
        if res:
            found = "; ".join(
                f"λ {r.wavelength:.5f} µm, Q {r.q:.0f}, ER {r.extinction_db:.1f} dB" for r in res
            )
            fsr = f"; FSR {np.mean(metrics.fsr(res)) * 1e3:.2f} nm" if len(res) > 1 else ""
            out.append(f"Meep resonances: {found}{fsr}.")
        else:
            out.append("Meep resonances: fewer than two complete resonances in the band.")
    out.append("")
    return out


def summary(tables: dict[str, list[Row]]) -> dict[str, Any]:
    """The "meep_comparison" section of results/<sha>.json."""
    tiers: dict[str, Any] = {}
    for tier_name, rows in tables.items():
        devices = {}
        for row in rows:
            entry: dict[str, Any] = {
                "status": row.status,
                "resolution": row.resolution,
                "passed": row.passed,
                "timing_s": {
                    "etalon_cuda": _wall(_run(row.etalon, "cuda")),
                    "etalon_numpy": _wall(_run(row.etalon, "numpy")),
                    "meep": _wall(row.meep.runs[0]) if row.meep else None,
                },
                "notes": row.notes,
            }
            if row.comparison is not None:
                entry["max_abs_s"] = row.comparison.max_abs_s
                entry["metrics"] = [
                    {
                        "name": m.name,
                        "value": m.value,
                        "gate": m.gate,
                        "unit": m.unit,
                        "passed": m.passed,
                    }
                    for m in row.comparison.metrics
                ]
                entry["cuda_vs_numpy"] = row.cuda_vs_numpy
            devices[row.device] = entry
        tiers[tier_name] = devices
    return {"generated": now_utc(), "tiers": tiers}


def _wall(run: RunRecord | None) -> dict[str, Any] | None:
    if run is None or run.status != "ok":
        return None
    return {"wall": run.wall_time_s, "extrapolated": run.extrapolated}


def write_report(
    cfg: BenchConfig, tiers: list[str], sha: str, results: Path = RESULTS, root: Path = BENCH
) -> Path:
    tables = {tier: build_rows(cfg, tier, root) for tier in tiers}
    results.mkdir(parents=True, exist_ok=True)
    md = results / f"{sha}.md"
    md.write_text(render_markdown(cfg, tables, sha), encoding="utf-8", newline="\n")
    update_record(sha, "meep_comparison", summary(tables), results)
    return md


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tier", action="append", help="tier(s) to report (default: all)")
    args = parser.parse_args(argv)
    cfg = load_config()
    tiers = args.tier or list(cfg.tiers)
    path = write_report(cfg, tiers, git_sha())
    print(path.read_text(encoding="utf-8"))
    print(f"wrote {path} and {path.with_suffix('.json')}")


if __name__ == "__main__":
    main()
