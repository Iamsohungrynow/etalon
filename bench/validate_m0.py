"""M0 validation report: vacuum dispersion, CPML reflection, source normalisation, throughput.

Writes bench/results/m0_vacuum.png and the "m0" section of bench/results/<git-sha>.json.

    python bench/validate_m0.py            # CUDA when available, NumPy otherwise
    python bench/validate_m0.py --numpy    # force the CPU reference backend
"""

import datetime
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a file: python bench/validate_m0.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import etalon as et
from bench.record import RESULTS, git_sha, update_record
from etalon.analysis import numerical_phase_velocity
from etalon.fdtd.backends import get_backend
from etalon.grid.yee import YeeGrid2D, courant_time_step
from etalon.validation import m0
from etalon.validation.throughput import measure_throughput

# Reference data-viz palette, light mode (validated: CVD ΔE 24.7, normal-vision ΔE 33.6)
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3de"
SERIES = {0.0: "#2a78d6", 45.0: "#eb6834"}
PROBES = {"side": "#2a78d6", "corner": "#eb6834"}


def style(ax: Any, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.tick_params(colors=INK_2, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.xaxis.label.set_color(INK_2)
    ax.yaxis.label.set_color(INK_2)


def plain_log_x(ax: Any) -> None:
    """Log x axis with plain tick labels (8, 10, 20, ...) instead of 2×10¹."""
    ax.set_xscale("log")
    ax.set_xticks([8, 10, 15, 20, 30, 40, 60, 80])
    ax.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())


def field_snapshot(backend: str) -> Any:
    sim = et.Simulation(
        size=(8.0, 8.0, 0.0),
        grid=et.UniformGrid(dl=0.05),
        boundary=et.PML(layers=12),
        sources=[
            et.PointSource(
                center=(0.0, 0.0, 0.0),
                component="Hz",
                pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.5),
            )
        ],
        monitors=[
            et.DFTMonitor(
                name="field", size=(8.0, 8.0, 0.0), wavelengths=[1.55], components=("Hz",)
            )
        ],
        run_time=200e-15,
        backend=backend,
    )
    return sim.run()["field"]["Hz"].isel(wavelength=0)


def main() -> None:
    backend = "numpy" if "--numpy" in sys.argv else "auto"
    resolved = get_backend(backend, "single")
    print(f"backend: {resolved.name} ({resolved.device})")

    dispersion = [c for dl in (0.1, 0.05, 0.025) for c in m0.dispersion_cases(dl, backend=backend)]
    reflection = m0.cpml_reflection_case(backend=backend)
    late = m0.late_time_case(backend=backend)
    green = m0.green_function_case(dl=0.05, backend=backend)
    hz = field_snapshot(backend)
    if resolved.name == "cuda":
        throughput = measure_throughput(region_cells=2000, steps=500, backend="cuda")
    else:
        throughput = measure_throughput(region_cells=500, steps=50, backend="numpy")

    # ---------------------------------------------------------------- figure
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.6), facecolor=SURFACE)
    (ax_v, ax_r), (ax_f, ax_p) = axes

    # (a) phase velocity vs resolution: theory lines, measured points
    n_dense = np.geomspace(8, 80, 200)
    unit = YeeGrid2D(
        nx=1,
        ny=1,
        dx=1.0,
        dy=1.0,
        dt=courant_time_step(0.99, 1.0, 1.0),
        pml_layers=0,
        x_min=0.0,
        y_min=0.0,
        z=0.0,
        courant=0.99,
    )
    for angle, color in SERIES.items():
        theory = numerical_phase_velocity(n_dense, unit, angle=angle)  # λ = N cells of 1 µm
        ax_v.plot(n_dense, theory, color=color, linewidth=2, label=f"Yee relation, {angle:g}°")
        cases = [c for c in dispersion if c.angle == angle]
        n_cells = np.concatenate([c.cells_per_wavelength for c in cases])
        v = np.concatenate([c.v_measured for c in cases])
        ax_v.plot(
            n_cells,
            v,
            "o",
            color=color,
            markersize=5.5,
            markeredgecolor=SURFACE,
            markeredgewidth=1.0,
            label=f"measured, {angle:g}°",
        )
        at = np.searchsorted(n_dense, 12.0)  # label where the two curves are far apart
        ax_v.annotate(
            f"{angle:g}°",
            (n_dense[at], theory[at]),
            xytext=(0, 8) if angle else (10, -10),
            textcoords="offset points",
            ha="center" if angle else "left",
            fontsize=9,
            color=INK,
        )
    ax_v.axhline(1.0, color=INK_2, linewidth=0.8, linestyle=":")
    plain_log_x(ax_v)
    ax_v.set_xlabel("cells per wavelength")
    ax_v.set_ylabel("phase velocity / c")
    ax_v.legend(fontsize=8, frameon=False, loc="lower right", labelcolor=INK)
    style(ax_v, "a  Numerical phase velocity, 2D vacuum (courant 0.99)")

    # (b) residual against the Yee relation
    for angle, color in SERIES.items():
        cases = [c for c in dispersion if c.angle == angle]
        n_cells = np.concatenate([c.cells_per_wavelength for c in cases])
        resid = np.concatenate([np.abs(c.v_measured / c.v_theory - 1) for c in cases])
        ax_r.plot(
            n_cells,
            resid,
            "o",
            color=color,
            markersize=5.5,
            markeredgecolor=SURFACE,
            markeredgewidth=1.0,
            label=f"{angle:g}°",
        )
    for level, text in ((5e-3, "M0 acceptance 5e-3"), (1e-3, "test threshold 1e-3")):
        ax_r.axhline(level, color=INK_2, linewidth=1, linestyle="--")
        ax_r.text(80, level, text, ha="right", va="bottom", fontsize=8, color=INK_2)
    plain_log_x(ax_r)
    ax_r.set_yscale("log")
    ax_r.set_ylim(1e-6, 2e-2)
    ax_r.set_xlabel("cells per wavelength")
    ax_r.set_ylabel("|v measured / v Yee − 1|")
    ax_r.legend(fontsize=8, frameon=False, loc="lower left", labelcolor=INK)
    style(ax_r, "b  Measured vs Yee dispersion relation")

    # (c) field map
    re = np.real(hz.values).T
    r = np.hypot(*np.meshgrid(hz.x, hz.y))
    re = re / np.abs(re[r > 1.0]).max()  # normalise outside 1 µm; the near field saturates
    image = ax_f.pcolormesh(
        hz.x, hz.y, re, cmap="RdBu_r", vmin=-1, vmax=1, shading="auto", rasterized=True
    )
    ax_f.set_aspect("equal")
    ax_f.set_xlabel("x (µm)")
    ax_f.set_ylabel("y (µm)")
    bar = fig.colorbar(image, ax=ax_f, shrink=0.85)
    bar.set_label("Re Hz / max beyond r = 1 µm", color=INK_2, fontsize=8)
    bar.ax.tick_params(labelsize=7, colors=INK_2)
    style(ax_f, "c  Re Hz at λ = 1.55 µm, region edge = PML interface")
    ax_f.grid(False)

    # (d) CPML reflection error over time
    t_fs = reflection.t * 1e15
    scale = np.abs(reflection.hz_reference).max(0)
    for k, probe in enumerate(reflection.probes):
        err = np.abs(reflection.hz_small[:, k] - reflection.hz_reference[:, k]) / scale[k]
        ax_p.semilogy(
            t_fs,
            np.maximum(err, 1e-12),
            color=PROBES[probe],
            linewidth=1.5,
            label=f"{probe} probe (max {20 * np.log10(reflection.error[k]):.0f} dB)",
        )
    for level, text in ((1e-3, "plan −60 dB"), (1e-4, "test guard −80 dB")):
        ax_p.axhline(level, color=INK_2, linewidth=1, linestyle="--")
        ax_p.text(t_fs[-1], level, text, ha="right", va="bottom", fontsize=8, color=INK_2)
    ax_p.set_ylim(1e-9, 1e-2)
    ax_p.set_xlabel("time (fs)")
    ax_p.set_ylabel("|Hz − Hz reference| / max|Hz reference|")
    ax_p.legend(fontsize=8, frameon=False, loc="upper left", labelcolor=INK)
    style(ax_p, "d  CPML reflection, 12 layers, probes 2 cells from the PML")

    sha = git_sha()
    green_error = float(np.abs(green.hz_measured / green.hz_analytic - 1).max())
    fig.suptitle(
        f"etalon {et.__version__} · M0 vacuum validation · {sha} · {resolved.device} · "
        f"{throughput.cell_updates_per_s / 1e9:.2f}e9 cell-updates/s · "
        f"Green's function |error| {green_error:.1e}",
        fontsize=10,
        color=INK,
        x=0.01,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    RESULTS.mkdir(exist_ok=True)
    png = RESULTS / "m0_vacuum.png"
    fig.savefig(png, dpi=150, facecolor=SURFACE)

    # ---------------------------------------------------------------- JSON record
    record = {
        "milestone": "M0",
        "git_sha": sha,
        "date": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "etalon_version": et.__version__,
        "backend": resolved.name,
        "device": resolved.device,
        "dispersion": [
            {
                "dl_um": c.dl,
                "angle_deg": c.angle,
                "cells_per_wavelength": [
                    float(np.min(c.cells_per_wavelength)),
                    float(np.max(c.cells_per_wavelength)),
                ],
                "max_abs_residual_vs_yee": float(np.max(np.abs(c.v_measured / c.v_theory - 1))),
                "min_v_over_c": float(np.min(c.v_measured)),
            }
            for c in dispersion
        ],
        "cpml_reflection": dict(zip(reflection.probes, map(float, reflection.error), strict=True)),
        "late_time_final_energy_rel": float(late.energy[-1] / np.max(late.energy)),
        "green_function_max_rel_error": green_error,
        "throughput": asdict(throughput),
    }
    out = update_record(sha, "m0", record)
    print(json.dumps(record, indent=2))
    print(f"wrote {png} and {out}")


if __name__ == "__main__":
    main()
