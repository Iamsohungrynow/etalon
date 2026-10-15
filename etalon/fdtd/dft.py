"""Where monitors and point sources sit on the Yee lattice, and the DFT phasors.

Two sampling rules, applied per axis (see etalon.DFTMonitor):

* size > 0  — every node of the component inside [center − size/2, center + size/2];
* size = 0  — linear interpolation between the two nodes that bracket the
  coordinate (one node with weight 1 when the coordinate is on a node).

Point sources use the size = 0 rule on both axes, i.e. bilinear weights.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from etalon.constants import C_0
from etalon.core.monitor import DFTMonitor
from etalon.grid.yee import TE_COMPONENTS, YeeGrid2D

_ON_NODE = 1e-9  # fraction of a cell below which a coordinate counts as on a node


@dataclass(frozen=True)
class AxisSampling:
    """Nodes taken along one axis, and how they combine into the output."""

    index: NDArray[np.int64]
    """Node indices along this axis."""
    coords: NDArray[np.float64]
    """Their coordinates, µm."""
    weights: NDArray[np.float64] | None
    """Interpolation weights onto ``point`` (size = 0), or None (raw nodes)."""
    point: float | None
    """The interpolated coordinate, µm, or None."""


def axis_sampling(
    nodes: NDArray[np.float64], center: float, size: float, what: str
) -> AxisSampling:
    """Sample a uniform node row ``nodes`` with the rules in the module docstring."""
    spacing = nodes[1] - nodes[0]
    if size > 0.0:
        tol = _ON_NODE * spacing
        lo, hi = center - size / 2.0, center + size / 2.0
        index = np.nonzero((nodes >= lo - tol) & (nodes <= hi + tol))[0].astype(np.int64)
        if index.size == 0:
            raise ValueError(
                f"{what} contains no grid node along this axis (thinner than one cell, "
                f"{spacing} µm); give it size 0 to interpolate instead"
            )
        return AxisSampling(index, nodes[index], None, None)
    position = (center - nodes[0]) / spacing
    i0 = math.floor(position)
    frac = position - i0
    if frac < _ON_NODE:
        index, weights = np.array([i0]), np.array([1.0])
    elif frac > 1.0 - _ON_NODE:
        index, weights = np.array([i0 + 1]), np.array([1.0])
    else:
        index, weights = np.array([i0, i0 + 1]), np.array([1.0 - frac, frac])
    if index[0] < 0 or index[-1] >= nodes.size:
        raise ValueError(f"{what} at {center} µm is outside the grid")
    index = index.astype(np.int64)
    return AxisSampling(index, nodes[index], weights, center)


@dataclass(frozen=True)
class ComponentSampling:
    """The nodes one monitor records for one field component."""

    monitor: str
    component: str
    wavelengths: NDArray[np.float64]
    """µm, in the order the monitor gave them."""
    x: AxisSampling
    y: AxisSampling
    flat_index: NDArray[np.int64]
    """Indices into the raveled (C-order) component array, x-major."""

    @property
    def frequencies(self) -> NDArray[np.float64]:
        """Hz."""
        return C_0 / self.wavelengths

    @property
    def is_magnetic(self) -> bool:
        return self.component.startswith("H")


def monitor_samplings(monitor: DFTMonitor, grid: YeeGrid2D) -> list[ComponentSampling]:
    """One ComponentSampling per recorded component of a monitor."""
    components = monitor.components or TE_COMPONENTS
    wavelengths = np.asarray(monitor.wavelengths, dtype=np.float64)
    samplings = []
    for component in components:
        x_nodes, y_nodes = grid.coords(component)
        what = f"monitor {monitor.name!r} ({component})"
        sx = axis_sampling(x_nodes, monitor.center[0], monitor.size[0], what)
        sy = axis_sampling(y_nodes, monitor.center[1], monitor.size[1], what)
        n_y = grid.shape(component)[1]
        flat = (sx.index[:, None] * n_y + sy.index[None, :]).ravel()
        samplings.append(
            ComponentSampling(monitor.name, component, wavelengths, sx, sy, flat.astype(np.int64))
        )
    return samplings


def dft_phasors(
    frequencies: NDArray[np.float64], times: NDArray[np.float64], dt: float
) -> NDArray[np.complex128]:
    """exp(+i 2π f t) Δt for every (time, frequency) pair, shape (n_t, n_f), in float64.

    Computed in double precision on the host and cast by the caller: the phase
    2π f t reaches ~10³ rad, where float32 would lose ~1e-4 rad.
    """
    phase = 2.0 * np.pi * times[:, None] * frequencies[None, :]
    return np.asarray(np.exp(1j * phase) * dt, dtype=np.complex128)
