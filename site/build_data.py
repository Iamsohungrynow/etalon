"""Data for the landing page (site/): real etalon runs, nothing made up.

Runs four small 2D TE simulations and the M0 validation cases, then writes
site/data.json: each field as int8 (normalised Re and Im of the DFT at one
wavelength, base64), a line cut, a recorded run log, and the validation curves.

    .venv/Scripts/python site/build_data.py
"""

import base64
import datetime
import json
import time
from pathlib import Path

import numpy as np

import etalon as et
from etalon.fdtd.solver import FDTDSolver
from etalon.validation import m0

OUT = Path(__file__).parent / "data.json"
WL = 1.55
SI, SIO2 = et.Medium(n=3.476, name="Si"), et.Medium(n=1.444, name="SiO2")


def pulse():
    return et.GaussianPulse(wavelength=WL, bandwidth=0.3)


def field_monitor(size):
    return et.DFTMonitor(name="field", size=size, wavelengths=[WL])


def cases():
    yield {
        "id": "SIM-01",
        "name": "Vacuum pulse",
        "title": "Point source in free space",
        "abstract": "A magnetic line source radiates a 1.55 µm pulse into 2D vacuum; "
        "the CPML absorbs it at the edges.",
        "keys": ["VACUUM", "CYLINDRICAL WAVE", "CPML", "HZ"],
        "component": "Hz",
        "sim": et.Simulation(
            size=(8.0, 8.0, 0.0), grid=et.UniformGrid(dl=0.04),
            sources=[et.PointSource(center=(-2.5, 0, 0), component="Hz", pulse=pulse())],
            monitors=[field_monitor((8.0, 8.0, 0.0))], run_time=150e-15, backend="cuda",
        ),
    }
    core = et.Box(center=(0, 0, 0), size=(20.0, 0.5, 0.22), medium=SI)
    yield {
        "id": "SIM-02",
        "name": "Strip waveguide",
        "title": "500 nm silicon strip in oxide",
        "abstract": "An in-plane dipole inside a 0.5 µm Si core (n = 3.476) in SiO2 "
        "(n = 1.444): the guided TE mode carries the light along x.",
        "keys": ["SILICON", "TE MODE", "GUIDED", "EY"],
        "component": "Ey",
        "sim": et.Simulation(
            size=(8.0, 4.0, 0.0), medium=SIO2, structures=[core], grid=et.UniformGrid(dl=0.025),
            sources=[et.PointSource(center=(-3.5, 0, 0), component="Ey", pulse=pulse())],
            monitors=[field_monitor((8.0, 4.0, 0.0))], run_time=200e-15, backend="cuda",
        ),
    }
    arms = [
        et.Box(center=(-1.75, -1.0, 0), size=(4.5, 0.5, 0.22), medium=SI),
        et.Box(center=(0.25, 1.25, 0), size=(0.5, 5.0, 0.22), medium=SI),
    ]
    yield {
        "id": "SIM-03",
        "name": "Sharp bend",
        "title": "90° corner in a silicon strip",
        "abstract": "The same strip turned through a sharp 90° corner: part of the light "
        "follows the bend, the rest scatters into the oxide.",
        "keys": ["BEND", "SCATTERING", "SILICON", "EY"],
        "component": "Ey",
        "sim": et.Simulation(
            size=(6.0, 6.0, 0.0), medium=SIO2, structures=arms, grid=et.UniformGrid(dl=0.025),
            sources=[et.PointSource(center=(-2.6, -1.0, 0), component="Ey", pulse=pulse())],
            monitors=[field_monitor((6.0, 6.0, 0.0))], run_time=250e-15, backend="cuda",
        ),
    }
    period, n_periods = 0.37, 8
    layers = [
        et.Box(center=(0.5 + i * period, 0, 0), size=(0.11, 20.0, 0.22), medium=SI)
        for i in range(n_periods)
    ]
    yield {
        "id": "SIM-04",
        "name": "Bragg mirror",
        "title": "Eight Si layers in oxide",
        "abstract": "A source in front of eight 110 nm silicon layers with a 370 nm "
        "period: much of the light reflects and interferes with itself.",
        "keys": ["BRAGG", "STOPBAND", "INTERFERENCE", "HZ"],
        "component": "Hz",
        "sim": et.Simulation(
            size=(8.0, 6.0, 0.0), medium=SIO2, structures=layers, grid=et.UniformGrid(dl=0.025),
            sources=[et.PointSource(center=(-2.0, 0, 0), component="Hz", pulse=pulse())],
            monitors=[field_monitor((8.0, 6.0, 0.0))], run_time=250e-15, backend="cuda",
        ),
    }


def quantize(a, scale):
    q = np.clip(np.round(a / scale * 127.0), -127, 127).astype(np.int8)
    return base64.b64encode(q.tobytes()).decode()


def run_case(case):
    sim = case["sim"]
    solver = FDTDSolver(sim)
    log, start = [], time.perf_counter()
    every = max(1, solver.n_steps // 40)
    while solver.n < solver.n_steps:
        solver.step()
        if solver.n % every == 0 or solver.n == solver.n_steps:
            solver.backend.synchronize()
            f = solver.fields()
            energy = float(sum(np.sum(v.astype(np.float64) ** 2 / (377.0 if k != "Hz" else 1 / 377.0))
                               for k, v in f.items()))
            log.append([solver.n, energy, time.perf_counter() - start])
    solver.backend.synchronize()
    wall = time.perf_counter() - start
    result = solver.result(wall)
    field = result["field"][case["component"]].isel(wavelength=0)
    data = np.asarray(field.values).T  # (y, x) for drawing
    step = max(1, int(np.ceil(max(data.shape) / 180)))
    data = data[::step, ::step]
    scale = float(np.abs(data).max())
    peak_log = max(e for _, e, _ in log) or 1.0
    eps = [[float(b.center[0]), float(b.center[1]), float(b.size[0]), float(b.size[1]),
            b.medium.n] for b in sim.structures]
    grid = result.grid
    return {
        "id": case["id"],
        "name": case["name"],
        "title": case["title"],
        "abstract": case["abstract"],
        "keys": case["keys"],
        "component": case["component"],
        "wavelength_um": WL,
        "shape": list(data.shape),
        "extent_um": [float(field.x.min()), float(field.x.max()),
                      float(field.y.min()), float(field.y.max())],
        "re": quantize(data.real, scale),
        "im": quantize(data.imag, scale),
        "structures": eps,
        "params": {
            "grid": f"{grid.nx} × {grid.ny} cells",
            "dx": f"Δx = {grid.dx * 1000:.0f} nm",
            "steps": f"{result.metadata['n_steps']} steps",
            "speed": f"{result.metadata['cell_updates_per_s'] / 1e6:.0f} M cell-updates/s",
        },
        "device": result.metadata["device"],
        "log": [[n, e / peak_log, t] for n, e, t in log],
        "cut": [float(v) for v in np.abs(data[data.shape[0] // 2]) / scale],
    }


def validation():
    cases = m0.dispersion_cases(0.1, backend="cuda") + m0.dispersion_cases(0.05, backend="cuda")
    curves = {}
    for angle in (0.0, 45.0):
        sel = [c for c in cases if c.angle == angle]
        n = np.concatenate([c.cells_per_wavelength for c in sel])
        order = np.argsort(n)
        curves[f"{angle:g}"] = {
            "cells_per_wavelength": n[order].round(3).tolist(),
            "measured": np.concatenate([c.v_measured for c in sel])[order].round(7).tolist(),
            "theory": np.concatenate([c.v_theory for c in sel])[order].round(7).tolist(),
        }
    reflection = m0.cpml_reflection_case(backend="cuda")
    return {
        "dispersion": curves,
        "max_residual": float(max(np.abs(c.v_measured / c.v_theory - 1).max() for c in cases)),
        "cpml_db": [round(20 * float(np.log10(e)), 1) for e in reflection.error],
    }


def main():
    out = {
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
        "etalon_version": et.__version__,
        "cases": [run_case(c) for c in cases()],
        "validation": validation(),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} kB)")
    for c in out["cases"]:
        print(c["id"], c["name"], c["shape"], c["params"], c["device"])
    print("validation:", out["validation"]["max_residual"], out["validation"]["cpml_db"])


if __name__ == "__main__":
    main()
