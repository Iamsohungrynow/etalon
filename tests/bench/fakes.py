"""Synthetic result files for the report tests: no Meep, no GPU."""

from pathlib import Path

import numpy as np

from bench.config import BenchConfig
from bench.devices import layout
from bench.schema import (
    DeviceResult,
    GridRecord,
    RunRecord,
    encode_complex,
    out_path,
    port_records,
    write_result,
)

GRID = GridRecord(
    dl_um=0.02,
    cells=(100, 100),
    cells_total=10_000,
    pml_um=1.0,
    courant_meep=0.5,
    courant_fraction=0.7071,
    dt_s=3.3e-17,
    steps=1000,
)


def ring_spectra(wl: np.ndarray, first=1.5435, fsr=0.008, fwhm=0.0017, depth=0.9):
    """Add-drop ring spectra: Airy drop peaks at first + k·fsr, through = 1 − drop."""
    f_coef = 1.0 / np.sin(np.pi * fwhm / (2 * fsr)) ** 2
    drop = depth / (1 + f_coef * np.sin(np.pi * (wl - first) / fsr) ** 2)
    through = 1.0 - drop
    return {
        "S11": np.full(wl.shape, 1e-3 + 0j),
        "S21": np.sqrt(through).astype(complex),
        "S31": np.sqrt(drop).astype(complex),
        "S41": np.full(wl.shape, 1e-3 + 0j),
    }


def default_spectra(cfg: BenchConfig, device: str) -> dict[str, np.ndarray]:
    """Plausible S for each device (phase ramps included)."""
    wl = cfg.device(device).band.wavelengths()
    phase = np.exp(1j * 2 * np.pi * 2.5 * 10 / wl)
    if device == "point2d":
        return {"T21": 0.448 * phase}
    if device in ("straight", "bend"):
        return {"S11": 1e-3 * phase, "S21": 0.999 * phase}
    if device == "dc":
        return {
            "S11": 1e-3 * phase,
            "S21": 1e-3 * phase,
            "S31": np.sqrt(0.55) * phase,
            "S41": 1j * np.sqrt(0.44) * phase,
        }
    if device == "mmi":
        return {"S11": 1e-3 * phase, "S21": np.sqrt(0.48) * phase, "S31": np.sqrt(0.48) * phase}
    return ring_spectra(wl)


def run_record(backend: str, s: dict[str, np.ndarray] | None, **kwargs) -> RunRecord:
    fields = {
        "backend": backend,
        "status": "ok",
        "resolution": 50,
        "grid": GRID,
        "run_time_s": 1e-12,
        "wall_time_s": 10.0,
        "stepping_time_s": 9.0,
        "final_decay": 1e-9,
        "s": {k: encode_complex(v) for k, v in (s or {}).items()},
    }
    fields.update(kwargs)
    return RunRecord(**fields)


def device_result(
    cfg: BenchConfig, tier: str, device: str, solver: str, runs: list[RunRecord], **kwargs
) -> DeviceResult:
    fields = {
        "device": device,
        "tier": tier,
        "solver": solver,
        "config_sha256": cfg.config_sha256(tier, device),
        "code_sha256": "0" * 64,
        "git_sha": "abc1234",
        "date": "2026-10-16T00:00:00+00:00",
        "wavelengths_um": cfg.device(device).band.wavelengths().tolist(),
        "ports": port_records(cfg, cfg.tier(tier), layout(cfg, device)),
        "runs": runs,
    }
    fields.update(kwargs)
    return DeviceResult(**fields)


def write(root: Path, result: DeviceResult) -> Path:
    path = out_path(result.solver, result.tier, result.device, root)
    write_result(path, result)
    return path
