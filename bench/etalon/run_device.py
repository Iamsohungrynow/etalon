"""etalon side of the benchmark: one device in one tier → bench/etalon/out/<tier>/<device>.json.

Runs in etalon's environment and never imports meep. Every number comes from
bench/config.yaml through bench.config and bench.devices, exactly as on the Meep side.

    python -m bench.etalon.run_device straight --tier 2d --backends cuda,numpy

What runs today (plan §3, option B): point2d, the convention check, runs on both backends.
The five reference devices need features that arrive in M1 (mode source, mode port monitor,
PolySlab, and for the 3D tier 3D itself). Until then ``build`` raises ``NeedsMilestone``
naming them, and the run is recorded with status "unsupported". When M1 lands, the M2
session writes each device's ``build`` and ``extract`` (contract in plan §6).
"""

import argparse
import platform
import sys
import time
from typing import Any

import numpy as np

import etalon as et
from bench.config import BenchConfig, Tier, load_config, pulse
from bench.devices import Layout, layout
from bench.record import git_sha
from bench.schema import (
    DeviceResult,
    GridRecord,
    RunRecord,
    code_sha256,
    encode_complex,
    now_utc,
    out_path,
    port_records,
    write_result,
)
from etalon.fdtd.capabilities import check_supported
from etalon.fdtd.solver import FDTDSolver
from etalon.grid.yee import build_yee_grid

ETALON_CODE_FILES = (
    "__init__.py",
    "config.py",
    "devices.py",
    "schema.py",
    "etalon/__init__.py",
    "etalon/run_device.py",
)

REQUIRED_API = {"ModeSource": "M1", "ModePortMonitor": "M1", "PolySlab": "M1"}
"""Public names the five reference devices need, and the milestone that adds them."""

NUMPY_CELL_UPDATES_PER_S = {2: 3e7, 3: 1e7}
"""Rough NumPy throughput (M0: 3e7 in 2D) for deciding whether a CPU run is affordable."""

PARTIAL_STEPS = 200
"""Steps timed when a CPU run is too long to run in full; the wall time is extrapolated."""


class NeedsMilestone(Exception):
    """The installed etalon cannot run this device yet."""

    def __init__(self, milestone: str, missing: list[str]) -> None:
        self.milestone = milestone
        self.missing = missing
        super().__init__(
            f"needs {milestone}: {', '.join(missing)} (not in etalon {et.__version__} yet)"
        )


def missing_features(dims: int) -> list[str]:
    """What the five reference devices need that this etalon lacks."""
    missing = [name for name in REQUIRED_API if not hasattr(et, name)]
    if dims == 3 and not _supports_3d():
        missing.append("3D")
    return missing


def _supports_3d() -> bool:
    probe = et.Simulation(
        size=(1.0, 1.0, 1.0),
        grid=et.UniformGrid(dl=0.1),
        sources=[
            et.PointSource(
                center=(0, 0, 0),
                component="Ey",
                pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.1),
            )
        ],
        run_time=1e-15,
    )
    try:
        check_supported(probe)
    except NotImplementedError:
        return False
    return True


def build(cfg: BenchConfig, tier: Tier, lay: Layout, backend: str) -> et.Simulation:
    """The etalon simulation of ``lay`` in ``tier`` (or NeedsMilestone)."""
    if lay.device == "point2d":
        return _point2d(cfg, tier, lay, backend)
    missing = missing_features(tier.dims)
    if missing:
        raise NeedsMilestone(REQUIRED_API.get(missing[0], "M1"), missing)
    # M1's API exists but this device's adapter has not been written yet.
    raise NeedsMilestone("M2", [f"bench adapter for {lay.device} (bench/etalon/run_device.py)"])


def extract(lay: Layout, result: Any) -> tuple[dict[str, Any], dict[str, list[float]]]:
    """S-parameters (encoded) and n_eff per port from a SimulationResult."""
    if lay.device == "point2d":
        h1 = result["probe1"]["Hz"].values
        h2 = result["probe2"]["Hz"].values
        return {"T21": encode_complex(h2 / h1)}, {}
    raise NeedsMilestone("M2", [f"bench adapter for {lay.device}"])  # pragma: no cover


def _point2d(cfg: BenchConfig, tier: Tier, lay: Layout, backend: str) -> et.Simulation:
    device = cfg.devices.point2d
    p = pulse(device.band)
    wavelengths = device.band.wavelengths()
    n_background = {"si": cfg.materials.si, "sio2": cfg.materials.sio2}[lay.background]
    return et.Simulation(
        center=(*lay.region_center, 0.0),
        size=(*lay.region_size, 0.0),
        medium=et.Medium(n=n_background),
        grid=et.UniformGrid(dl=tier.dl),
        boundary=et.PML(layers=tier.pml_layers),
        sources=[
            et.PointSource(
                center=(*lay.source_center, 0.0),
                component="Hz",
                pulse=et.GaussianPulse(wavelength=p.wavelength, bandwidth=p.bandwidth),
            )
        ],
        monitors=[
            et.DFTMonitor(
                name=f"probe{i}", center=(x, y, 0.0), wavelengths=wavelengths, components=("Hz",)
            )
            for i, (x, y) in enumerate(lay.probes, start=1)
        ],
        run_time=device.run_time_fs * 1e-15,
        courant=tier.courant_etalon,
        precision=cfg.etalon.precision,
        backend=backend,
    )


def cuda_available() -> bool:
    try:
        import cupy

        return bool(cupy.cuda.runtime.getDeviceCount() > 0)
    except Exception:
        return False


def run_backend(cfg: BenchConfig, tier_name: str, lay: Layout, backend: str) -> RunRecord:
    """Run ``lay`` on one backend and describe the run (never raises for an expected gap)."""
    tier = cfg.tier(tier_name)
    device = cfg.device(lay.device)
    base: dict[str, Any] = {
        "backend": backend,
        "resolution": tier.resolution,
        "run_time_s": device.run_time_fs * 1e-15,
        "precision": cfg.etalon.precision,
        "versions": _versions(backend),
        "hardware": _hardware(),
    }
    try:
        sim = build(cfg, tier, lay, backend)
    except NeedsMilestone as gap:
        return RunRecord(status="unsupported", needs=gap.milestone, message=str(gap), **base)
    if backend == "cuda" and not cuda_available():
        return RunRecord(status="skipped", message="no CUDA device (CuPy or a GPU missing)", **base)

    grid = build_yee_grid(sim)
    steps = grid.n_steps(sim.run_time)
    record = GridRecord(
        dl_um=tier.dl,
        cells=(grid.nx, grid.ny),
        cells_total=grid.n_cells,
        pml_um=tier.pml,
        courant_meep=tier.courant_meep,
        courant_fraction=tier.courant_etalon,
        dt_s=grid.dt,
        steps=steps,
    )
    if backend == "numpy":
        estimate = grid.n_cells * steps / NUMPY_CELL_UPDATES_PER_S[tier.dims]
        limit = 60.0 * cfg.etalon.cpu_full_run_max_minutes
        if estimate > limit:
            return _partial_run(sim, base, record, limit)

    started = time.perf_counter()
    result = sim.run()
    s, n_eff = extract(lay, result)
    wall = time.perf_counter() - started
    base["hardware"] = {**base["hardware"], "device": result.metadata["device"]}
    return RunRecord(
        status="ok",
        grid=record,
        wall_time_s=wall,
        stepping_time_s=float(result.metadata["wall_time_s"]),
        s=s,
        n_eff=n_eff,
        extra={"cell_updates_per_s": result.metadata["cell_updates_per_s"]},
        **base,
    )


def _partial_run(
    sim: et.Simulation, base: dict[str, Any], record: GridRecord, limit: float
) -> RunRecord:
    """Time PARTIAL_STEPS steps and extrapolate the wall time; no S-parameters."""
    started = time.perf_counter()
    solver = FDTDSolver(sim)
    setup = time.perf_counter() - started
    started = time.perf_counter()
    for _ in range(min(PARTIAL_STEPS, solver.n_steps)):
        solver.step()
    solver.backend.synchronize()
    per_step = (time.perf_counter() - started) / min(PARTIAL_STEPS, solver.n_steps)
    stepping = per_step * solver.n_steps
    return RunRecord(
        status="ok",
        grid=record,
        wall_time_s=setup + stepping,
        stepping_time_s=stepping,
        extrapolated=True,
        message=f"full run would exceed {limit / 60:.0f} min; timed {PARTIAL_STEPS} steps",
        **base,
    )


def _versions(backend: str) -> dict[str, str]:
    versions = {
        "etalon": et.__version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    if backend == "cuda":
        try:
            import cupy

            versions["cupy"] = cupy.__version__
        except Exception:
            pass
    return versions


def _hardware() -> dict[str, str | int | None]:
    return {"cpu": _cpu_name(), "processes": 1, "platform": platform.platform()}


def _cpu_name() -> str:
    """Marketing name of the CPU (Windows registry, Linux /proc/cpuinfo), else platform's."""
    try:
        if sys.platform == "win32":
            import winreg

            key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                return str(winreg.QueryValueEx(handle, "ProcessorNameString")[0]).strip()
        with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
            for line in cpuinfo:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def run_device(
    cfg: BenchConfig, tier_name: str, device: str, backends: list[str], sha: str
) -> DeviceResult:
    tier = cfg.tier(tier_name)
    lay = layout(cfg, device)
    runs = [run_backend(cfg, tier_name, lay, backend) for backend in backends]
    return DeviceResult(
        device=device,
        tier=tier_name,
        solver="etalon",
        config_sha256=cfg.config_sha256(tier_name, device),
        code_sha256=code_sha256(ETALON_CODE_FILES),
        git_sha=sha,
        date=now_utc(),
        wavelengths_um=cfg.device(device).band.wavelengths().tolist(),
        ports=port_records(cfg, tier, lay),
        runs=runs,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("device")
    parser.add_argument("--tier", default="2d")
    parser.add_argument("--backends", default="cuda,numpy", help="comma-separated: cuda, numpy")
    parser.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")
    args = parser.parse_args(argv)
    cfg = load_config(overrides=args.overrides)
    if args.device not in cfg.tier(args.tier).devices:
        raise SystemExit(f"device {args.device!r} is not in tier {args.tier!r}")
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    result = run_device(cfg, args.tier, args.device, backends, git_sha())
    path = out_path("etalon", args.tier, args.device)
    write_result(path, result)
    for run in result.runs:
        timing = f"{run.wall_time_s:.2f} s" if run.wall_time_s is not None else "-"
        print(
            f"etalon {args.device} {args.tier} {run.backend}: {run.status} {timing} "
            f"{run.message or ''}".rstrip()
        )
    print(f"-> {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
