"""Meep side of the benchmark: one device in one tier → bench/meep/out/<tier>/<device>.json.

This is the only module that imports meep (GPL-2.0-or-later). It runs in the Meep
environment (bench/meep/env.yaml), from the repository root, started by
bench/run_meep_comparison.py:

    mpirun -np 6 python -m mpi4py -m bench.meep.run_device straight --tier 2d

It never imports etalon. Every number comes from bench/config.yaml through bench.config
and bench.devices; this script only maps them onto Meep's public Python API
(meep.readthedocs.io, Python User Interface). Conventions, plan §6–§7:

* Meep length unit a = 1 µm: frequency 1/λ, time in a/c. The cell is the region plus the
  PML on every side, centred on the origin; positions are shifted by the region centre.
* Mode parity EVEN_Z, band 1. In 2D that is the Hz polarisation (Ex, Ey, Hz), etalon's
  2D TE; in 3D the cladding is symmetric in z, so EVEN_Z band 1 is TE0.
* S_i1 = a_i(outgoing) / a_1(incident), with power-normalised mode coefficients from
  get_eigenmode_coefficients in the same run; alpha[..., 0] travels along +axis.
"""

import argparse
import datetime
import platform
import sys
import time
from pathlib import Path
from typing import Any

import meep as mp
import numpy as np

from bench.config import BenchConfig, Tier, load_config, meep_time, pulse
from bench.devices import Layout, layout, mode_plane
from bench.schema import (
    DeviceResult,
    GridRecord,
    RunRecord,
    code_sha256,
    encode_complex,
    out_path,
    port_records,
    write_result,
)

PARITY = mp.EVEN_Z
SAMPLE_EVERY = 0.25
"""Interval for the field-decay probes, Meep time units (≈ 0.83 fs; ≥ 6 samples per period)."""


class DecayProbe:
    """Peak |field|² at a point, and its largest value over the last 10 % of the run."""

    def __init__(self, component: Any, point: Any, until: float) -> None:
        self.component, self.point, self.late_after = component, point, 0.9 * until
        self.peak = 0.0
        self.late = 0.0

    def step_function(self) -> Any:
        """A plain function of the simulation, as Meep's step functions must be."""

        def sample(sim: mp.Simulation) -> None:
            value = abs(sim.get_field_point(self.component, self.point)) ** 2
            self.peak = max(self.peak, value)
            if sim.meep_time() >= self.late_after:
                self.late = max(self.late, value)

        return sample


def final_decay(probes: list[DecayProbe]) -> float:
    """Largest late |field|² over all output probes / largest peak over all of them.

    Normalising by the overall peak, not each probe's own, keeps a nearly dark port
    (a ring's add port, a coupler's isolated port) from reading as unconverged noise.
    """
    peak = max(probe.peak for probe in probes)
    return max(probe.late for probe in probes) / peak if peak > 0 else float("nan")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("device")
    parser.add_argument("--tier", default="2d")
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="config override, e.g. tiers.2d.pml=0.5",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="output file (default: out/<tier>/<device>.json)"
    )
    parser.add_argument("--git-sha", default="unknown", help="etalon commit, for provenance")
    args = parser.parse_args(argv)

    cfg = load_config(overrides=args.overrides)
    tier = cfg.tier(args.tier)
    if args.device not in tier.devices:
        raise SystemExit(f"device {args.device!r} is not in tier {args.tier!r}")
    lay = layout(cfg, args.device)
    result = run_device(cfg, args.tier, tier, lay, args.git_sha)
    if mp.am_master():
        path = args.out or out_path("meep", args.tier, args.device)
        write_result(path, result)
        run = result.runs[0]
        print(
            f"meep {args.device} {args.tier}: wall {run.wall_time_s:.1f} s, "
            f"final decay {run.final_decay:.2e} -> {path}",
            flush=True,
        )


def run_device(
    cfg: BenchConfig, tier_name: str, tier: Tier, lay: Layout, git_sha: str
) -> DeviceResult:
    device = cfg.device(lay.device)
    wavelengths = device.band.wavelengths()
    freqs = 1.0 / wavelengths
    p = pulse(device.band)
    until = meep_time(device.run_time_fs)
    shift = np.array(lay.region_center)

    def at(x: float, y: float, z: float = 0.0) -> mp.Vector3:
        """Meep position of an absolute (µm) point: the cell is centred on the region."""
        return mp.Vector3(x - shift[0], y - shift[1], z)

    def size3(size: tuple[float, float, float]) -> mp.Vector3:
        return mp.Vector3(*size)

    started = time.perf_counter()
    n_core = cfg.materials.si if tier.dims == 3 else tier.core_index
    materials = {"core": mp.Medium(index=n_core), "cladding": mp.Medium(index=cfg.materials.sio2)}
    background = {"si": cfg.materials.si, "sio2": cfg.materials.sio2}[lay.background]
    thickness = cfg.strip.thickness
    z_base, height = (-thickness / 2, thickness) if tier.dims == 3 else (-1.0, 2.0)
    geometry = [
        mp.Prism(
            vertices=[at(x, y, z_base) for x, y in poly.vertices],
            height=height,
            axis=mp.Vector3(0, 0, 1),
            material=materials[poly.material],
        )
        for poly in lay.polygons
    ]
    sx, sy = lay.region_size
    sz = tier.z_span if tier.dims == 3 else 0.0
    cell = mp.Vector3(sx + 2 * tier.pml, sy + 2 * tier.pml, sz + 2 * tier.pml if sz else 0.0)
    source_time = mp.GaussianSource(
        frequency=p.meep_frequency, fwidth=p.meep_fwidth, cutoff=p.meep_cutoff
    )

    if lay.ports:
        centre, size = mode_plane(lay.source_center, "-x", cfg.ports, tier)
        sources = [
            mp.EigenModeSource(
                src=source_time,
                center=at(*centre),
                size=size3(size),
                direction=mp.X,
                eig_kpoint=mp.Vector3(1, 0, 0),
                eig_band=1,
                eig_parity=PARITY,
                eig_match_freq=True,
            )
        ]
    else:  # point2d: Hz line source
        sources = [mp.Source(source_time, component=mp.Hz, center=at(*lay.source_center))]

    sim = mp.Simulation(
        cell_size=cell,
        resolution=tier.resolution,
        boundary_layers=[mp.PML(tier.pml)],
        geometry=geometry,
        default_material=mp.Medium(index=background),
        sources=sources,
        Courant=tier.courant_meep,
        eps_averaging=True,
    )

    monitors = {}
    probes: list[tuple[str, Any, Any]] = []
    decay_probes: list[DecayProbe] = []
    if lay.ports:
        for port in lay.ports:
            centre, size = mode_plane(port.center, port.normal, cfg.ports, tier)
            monitors[port.name] = sim.add_mode_monitor(
                freqs.tolist(), mp.ModeRegion(center=at(*centre), size=size3(size))
            )
            if port.name != "1":
                component = mp.Hz if tier.dims == 2 else (mp.Ey if port.axis == "x" else mp.Ex)
                decay_probes.append(DecayProbe(component, at(*port.center), until))
    else:
        # A zero-size DFT volume returns 0, so record a 2Δ × 2Δ box around each probe and
        # read the Hz node at its centre (the probes sit on Hz nodes; checked below).
        box = mp.Vector3(2 * tier.dl, 2 * tier.dl)
        for i, (px, py) in enumerate(lay.probes, start=1):
            dft = sim.add_dft_fields([mp.Hz], freqs.tolist(), center=at(px, py), size=box)
            probes.append((str(i), dft, at(px, py)))
        decay_probes.append(DecayProbe(mp.Hz, at(*lay.probes[-1]), until))

    step_funcs: list[Any] = [
        mp.at_every(SAMPLE_EVERY, probe.step_function()) for probe in decay_probes
    ]
    harminv = None
    if lay.device == "ring":
        drop = next(port for port in lay.ports if port.label == "drop")
        df = 1.0 / device.band.min - 1.0 / device.band.max
        component = mp.Hz if tier.dims == 2 else mp.Ey
        harminv = mp.Harminv(component, at(*drop.center), p.meep_frequency, 2 * df)
        step_funcs.append(mp.after_sources(harminv))

    sim.init_sim()
    stepping_started = time.perf_counter()
    sim.run(*step_funcs, until=until)
    stepping = time.perf_counter() - stepping_started

    s: dict[str, Any] = {}
    n_eff: dict[str, list[float]] = {}
    extra: dict[str, Any] = {}
    if lay.ports:
        alphas, kdoms = {}, {}
        for port in lay.ports:
            coeffs = sim.get_eigenmode_coefficients(monitors[port.name], [1], eig_parity=PARITY)
            alphas[port.name] = np.asarray(coeffs.alpha)[0]  # (nfreq, 2): [:, 0] along +axis
            kdoms[port.name] = coeffs.kdom
        incident = alphas["1"][:, 0]  # port 1 faces −x, the source launches along +x
        for port in lay.ports:
            outgoing = alphas[port.name][:, 0 if port.sign > 0 else 1]
            s[f"S{port.name}1"] = encode_complex(outgoing / incident)
            axis = 0 if port.axis == "x" else 1
            k = np.array([abs(kd[axis]) for kd in kdoms[port.name]])
            n_eff[port.name] = (k / freqs).tolist()
        extra["incident_abs"] = np.abs(incident).tolist()
        extra["port1_backward_over_forward"] = float(
            np.max(np.abs(alphas["1"][:, 1]) / np.abs(incident))
        )
    else:
        values = {}
        for name, dft, point in probes:
            xs, ys = (np.asarray(c) for c in sim.get_array_metadata(dft_cell=dft)[:2])
            i, j = int(np.argmin(np.abs(xs - point.x))), int(np.argmin(np.abs(ys - point.y)))
            if abs(xs[i] - point.x) > 1e-6 or abs(ys[j] - point.y) > 1e-6:
                raise RuntimeError(f"probe {name} at {point} is not on a Meep Hz node")
            values[name] = np.array(
                [np.asarray(sim.get_dft_array(dft, mp.Hz, f))[i, j] for f in range(freqs.size)]
            )
        s["T21"] = encode_complex(values["2"] / values["1"])
        extra["probe1_abs"] = np.abs(values["1"]).tolist()
    if harminv is not None:
        extra["harminv"] = [
            {"wavelength_um": 1.0 / m.freq, "Q": m.Q, "amp": abs(m.amp), "err": m.err}
            for m in harminv.modes
        ]
    wall = time.perf_counter() - started

    dims = 3 if tier.dims == 3 else 2
    cells = tuple(round(c * tier.resolution) for c in (cell.x, cell.y, cell.z)[:dims])
    dt_meep = tier.courant_meep / tier.resolution
    run = RunRecord(
        backend="meep-mpi",
        status="ok",
        versions={
            "meep": str(mp.__version__),
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        hardware={
            "cpu": _cpu_name(),
            "processes": mp.count_processors(),
            "gpu": None,
            "platform": platform.platform(),
        },
        precision="double",
        resolution=tier.resolution,
        grid=GridRecord(
            dl_um=tier.dl,
            cells=cells,
            cells_total=int(np.prod(cells)),
            pml_um=tier.pml,
            courant_meep=tier.courant_meep,
            courant_fraction=tier.courant_etalon,
            dt_s=dt_meep * 1e-6 / 299_792_458.0,
            steps=round(until / dt_meep),
        ),
        run_time_s=device.run_time_fs * 1e-15,
        wall_time_s=wall,
        stepping_time_s=stepping,
        final_decay=final_decay(decay_probes),
        s=s,
        n_eff=n_eff,
        extra=extra,
    )
    return DeviceResult(
        device=lay.device,
        tier=tier_name,
        solver="meep",
        config_sha256=cfg.config_sha256(tier_name, lay.device),
        code_sha256=code_sha256(),
        git_sha=git_sha,
        date=datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        wavelengths_um=wavelengths.tolist(),
        ports=port_records(cfg, tier, lay),
        runs=[run],
    )


def _cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


if __name__ == "__main__":
    main(sys.argv[1:])
