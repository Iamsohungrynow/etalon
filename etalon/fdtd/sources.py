"""Source time signals and point-source injection.

Injection follows Maxwell's equations with electric and magnetic current
densities (Taflove & Hagness, 3rd ed., ch. 3):

    ∇×H =  ε ∂E/∂t + J      →  E^(n+1) = E^n + (Δt/ε)(∇×H)^(n+½) − (Δt/ε) J^(n+½)
    ∇×E = −μ ∂H/∂t − M      →  H^(n+½) = H^(n−½) − (Δt/μ)(∇×E)^n − (Δt/μ) M^n

so J is sampled at t = (n + ½)Δt and M at t = nΔt, the times each update
consumes them. A point source of strength ``amplitude · g(t)`` becomes a
current density amplitude · g(t) / (Δx Δy) (Δ in metres) shared bilinearly
between the nearest nodes of its component.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from etalon.constants import EPSILON_0, MU_0, UM
from etalon.core.source import GaussianPulse, PointSource
from etalon.fdtd.dft import axis_sampling
from etalon.grid.yee import YeeGrid2D


def pulse_signal(pulse: GaussianPulse, t: float | NDArray[np.float64]) -> NDArray[np.float64]:
    """g(t) = amplitude · exp(−(t − t0)²/(2τ²)) · sin(2π f0 (t − t0)); t in s."""
    s = np.asarray(t, dtype=np.float64) - pulse.delay
    envelope = np.exp(-(s**2) / (2.0 * pulse.width**2))
    return pulse.amplitude * envelope * np.sin(2.0 * np.pi * pulse.frequency * s)


@dataclass(frozen=True)
class PointInjection:
    """A point source resolved onto the grid: which nodes, and how much per unit g(t)."""

    component: str
    i: NDArray[np.int64]
    j: NDArray[np.int64]
    weights: NDArray[np.float64]
    """Bilinear weights, summing to 1."""
    coefficient: NDArray[np.float64]
    """Field change per unit amplitude·g(t): (Δt/ε or Δt/μ) · weight / (Δx Δy)."""
    pulse: GaussianPulse

    @property
    def is_magnetic(self) -> bool:
        return self.component.startswith("H")

    def sample_time(self, n: int, dt: float) -> float:
        """Time at which the update of step n consumes this source: nΔt (M) or (n+½)Δt (J)."""
        return n * dt if self.is_magnetic else (n + 0.5) * dt

    def delta(self, n: int, dt: float) -> NDArray[np.float64]:
        """Amount to subtract from the field at the nodes during step n."""
        return self.coefficient * pulse_signal(self.pulse, self.sample_time(n, dt))


def point_injection(
    source: PointSource, grid: YeeGrid2D, eps_r: dict[str, NDArray[np.float64]]
) -> PointInjection:
    """Resolve a point source onto the nodes of its component."""
    x_nodes, y_nodes = grid.coords(source.component)
    what = f"source at {source.center}"
    sx = axis_sampling(x_nodes, source.center[0], 0.0, what)
    sy = axis_sampling(y_nodes, source.center[1], 0.0, what)
    assert sx.weights is not None and sy.weights is not None
    i = np.repeat(sx.index, sy.index.size)
    j = np.tile(sy.index, sx.index.size)
    weights = np.outer(sx.weights, sy.weights).ravel()
    area = (grid.dx * UM) * (grid.dy * UM)
    if source.component.startswith("H"):
        update = np.full(weights.shape, grid.dt / MU_0)
    else:
        update = grid.dt / (EPSILON_0 * eps_r[source.component][i, j])
    return PointInjection(
        component=source.component,
        i=i,
        j=j,
        weights=weights,
        coefficient=update * weights / area,
        pulse=source.pulse,
    )
