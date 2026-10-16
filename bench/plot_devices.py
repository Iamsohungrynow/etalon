"""Validation plot of the bench geometry: bench/results/bench_devices.png.

Every device as both codes build it: strip polygons, simulation region, the 2D tier's PML,
port planes (numbered) and the source plane.

    python -m bench.plot_devices
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PolygonPatch
from matplotlib.patches import Rectangle

from bench.config import DEVICE_NAMES, load_config
from bench.devices import layout

RESULTS = Path(__file__).parent / "results"

# Reference data-viz palette, light mode (as in validate_m0.py)
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3de"
CORE, CLADDING, PML, PORT, SOURCE = "#2a78d6", "#fcfcfb", "#ece9e2", "#eb6834", "#1f9e6e"


def main() -> None:
    cfg = load_config()
    tier = cfg.tier("2d")
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4), facecolor=SURFACE)
    for ax, name in zip(axes.flat, DEVICE_NAMES, strict=True):
        lay = layout(cfg, name)
        (x_lo, x_hi), (y_lo, y_hi) = lay.region_bounds
        p = tier.pml
        ax.add_patch(
            Rectangle((x_lo - p, y_lo - p), x_hi - x_lo + 2 * p, y_hi - y_lo + 2 * p, color=PML)
        )
        ax.add_patch(Rectangle((x_lo, y_lo), x_hi - x_lo, y_hi - y_lo, color=SURFACE))
        for poly in lay.polygons:
            color = CORE if poly.material == "core" else CLADDING
            ax.add_patch(PolygonPatch(poly.vertices, closed=True, color=color, linewidth=0))
        half = cfg.ports.width / 2
        for port in lay.ports:
            x, y = port.center
            if port.axis == "x":
                ax.plot([x, x], [y - half, y + half], color=PORT, linewidth=2)
            else:
                ax.plot([x - half, x + half], [y, y], color=PORT, linewidth=2)
            nudge = 0.04 * max(x_hi - x_lo, y_hi - y_lo)  # label just outside the plane
            dx = nudge * port.sign if port.axis == "x" else 0.0
            dy = nudge * port.sign if port.axis == "y" else 0.0
            ax.annotate(
                port.name,
                (x + dx, y + dy),
                ha="center",
                va="center",
                fontsize=9,
                color=PORT,
                fontweight="bold",
            )
        sx, sy = lay.source_center
        if lay.ports:
            ax.plot([sx, sx], [sy - half, sy + half], color=SOURCE, linewidth=2, linestyle="--")
        else:
            ax.plot([sx], [sy], "o", color=SOURCE, markersize=6)
            for px, py in lay.probes:
                ax.plot([px], [py], "s", color=PORT, markersize=6)
        ax.set_xlim(x_lo - p, x_hi + p)
        ax.set_ylim(y_lo - p, y_hi + p)
        ax.set_aspect("equal")
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=INK_2, labelsize=8)
        for side in ax.spines.values():
            side.set_color(GRID)
        ax.set_xlabel("x (µm)", color=INK_2, fontsize=8)
        ax.set_ylabel("y (µm)", color=INK_2, fontsize=8)
        ports = ", ".join(f"{q.name} {q.label}" for q in lay.ports) or "Hz source, 2 probes"
        ax.set_title(
            f"{name}  ({ports})",
            loc="left",
            fontsize=9,
            color=INK,
            fontweight="bold",
        )
    fig.suptitle(
        "etalon vs Meep bench geometry (bench/config.yaml) · blue: strip core · orange: port planes"
        f" · green dashed: mode source · grey: 2D-tier PML ({tier.pml} µm)",
        fontsize=10,
        color=INK,
        x=0.01,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / "bench_devices.png"
    fig.savefig(out, dpi=140, facecolor=SURFACE)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
