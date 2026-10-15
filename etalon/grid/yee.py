"""Uniform 2D Yee grid for TE fields (Ex, Ey, Hz).

Node positions (Taflove & Hagness, 3rd ed., ch. 3), with i, j counting cells
from the outer corner of the PML:

    Hz[i, j]  at ((i + ½)Δx, (j + ½)Δy)     shape (nx,     ny)
    Ex[i, j]  at ((i + ½)Δx,  j      Δy)     shape (nx,     ny + 1)
    Ey[i, j]  at ( i      Δx, (j + ½)Δy)     shape (nx + 1, ny)

Arrays are C-ordered with y fastest. Everything in this module is in API
units: µm and seconds.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from etalon.constants import C_0
from etalon.core.simulation import Simulation

TE_COMPONENTS = ("Ex", "Ey", "Hz")

# For each component: does it sit on half nodes (True) or integer nodes (False) along x, y?
_HALF_NODES = {"Hz": (True, True), "Ex": (True, False), "Ey": (False, True)}


@dataclass(frozen=True)
class YeeGrid2D:
    """Cell counts, spacings, time step and node coordinates of a 2D TE run."""

    nx: int
    """Cells along x, PML included."""
    ny: int
    """Cells along y, PML included."""
    dx: float
    """Cell size along x, µm."""
    dy: float
    """Cell size along y, µm."""
    dt: float
    """Time step, s."""
    pml_layers: int
    """PML cells on each face."""
    x_min: float
    """x of the outer PML corner (integer node i = 0), µm."""
    y_min: float
    """y of the outer PML corner (integer node j = 0), µm."""
    z: float
    """The simulated plane, µm."""
    courant: float
    """Δt as a fraction of the Courant limit."""

    @property
    def n_cells(self) -> int:
        """Total number of cells, PML included."""
        return self.nx * self.ny

    @property
    def region_cells(self) -> tuple[int, int]:
        """Cells inside the simulation region, PML excluded."""
        return self.nx - 2 * self.pml_layers, self.ny - 2 * self.pml_layers

    def shape(self, component: str) -> tuple[int, int]:
        """Array shape of a field component."""
        half_x, half_y = _HALF_NODES[component]
        return (self.nx if half_x else self.nx + 1, self.ny if half_y else self.ny + 1)

    def coords(self, component: str) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """x and y node coordinates (µm) along the two array axes of a component."""
        half_x, half_y = _HALF_NODES[component]
        n_x, n_y = self.shape(component)
        x = self.x_min + (np.arange(n_x) + (0.5 if half_x else 0.0)) * self.dx
        y = self.y_min + (np.arange(n_y) + (0.5 if half_y else 0.0)) * self.dy
        return np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)

    def n_steps(self, run_time: float) -> int:
        """Time steps needed to cover run_time (s)."""
        return math.ceil(round(run_time / self.dt, 9))


def cells_along(size: float, dl: float) -> int:
    """N = ceil(size / dl), ignoring float noise (0.56 / 0.01 = 56.00000000000001 → 56)."""
    return math.ceil(round(size / dl, 9))


def courant_time_step(courant: float, dx: float, dy: float) -> float:
    """Δt = courant / (c sqrt(1/Δx² + 1/Δy²)), s, with Δx, Δy in µm.

    The 2D Courant–Friedrichs–Lewy limit of the Yee scheme
    (Taflove & Hagness, 3rd ed., ch. 4) scaled by ``courant`` ≤ 1.
    """
    return courant / (C_0 * math.sqrt(1.0 / dx**2 + 1.0 / dy**2))


def build_yee_grid(sim: Simulation) -> YeeGrid2D:
    """The Yee grid of a 2D simulation: region cells plus PML cells outside it."""
    if not sim.is_2d:
        raise NotImplementedError("3D grids arrive in M1; set size_z = 0 for a 2D simulation")
    layers = sim.boundary.layers
    n_x = cells_along(sim.size[0], sim.grid.dl)
    n_y = cells_along(sim.size[1], sim.grid.dl)
    dx = sim.size[0] / n_x
    dy = sim.size[1] / n_y
    return YeeGrid2D(
        nx=n_x + 2 * layers,
        ny=n_y + 2 * layers,
        dx=dx,
        dy=dy,
        dt=courant_time_step(sim.courant, dx, dy),
        pml_layers=layers,
        x_min=sim.center[0] - sim.size[0] / 2.0 - layers * dx,
        y_min=sim.center[1] - sim.size[1] / 2.0 - layers * dy,
        z=sim.center[2],
        courant=sim.courant,
    )
