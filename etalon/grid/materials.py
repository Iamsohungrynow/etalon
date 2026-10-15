"""Relative permittivity on the Yee nodes (staircase, no subpixel smoothing)."""

import numpy as np
from numpy.typing import NDArray

from etalon.core.simulation import Simulation
from etalon.grid.yee import YeeGrid2D

_TOL = 1e-9  # µm; a node exactly on a box face counts as inside


def permittivity_on_nodes(sim: Simulation, grid: YeeGrid2D) -> dict[str, NDArray[np.float64]]:
    """ε_r at the Ex and Ey nodes of a 2D grid.

    Each node takes the medium of the last structure that contains it (faces
    included), or the background medium. A box takes part when the simulated
    plane z = grid.z lies within its z extent. Nodes inside the PML are filled
    the same way, so structures that cross the region boundary continue into it.
    Subpixel smoothing (Farjadpour et al. 2006) replaces this in M1.
    """
    eps: dict[str, NDArray[np.float64]] = {}
    for component in ("Ex", "Ey"):
        x, y = grid.coords(component)
        x_nodes, y_nodes = np.meshgrid(x, y, indexing="ij")
        values = np.full(x_nodes.shape, sim.medium.permittivity)
        for box in sim.structures:
            (cx, cy, cz), (sx, sy, sz) = box.center, box.size
            if abs(grid.z - cz) > sz / 2.0 + _TOL:
                continue
            inside = (np.abs(x_nodes - cx) <= sx / 2.0 + _TOL) & (
                np.abs(y_nodes - cy) <= sy / 2.0 + _TOL
            )
            values[inside] = box.medium.permittivity
        eps[component] = values
    return eps
