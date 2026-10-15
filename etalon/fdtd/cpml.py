"""CPML coefficient profiles along one axis (Roden & Gedney 2000).

The derivative ∂F/∂w normal to a PML face is replaced by

    (1/κ) ∂F/∂w + ψ,     ψ ← b ψ + c ∂F/∂w,
    b = exp(−(σ/κ + α) Δt/ε0),     c = σ (b − 1) / (σ κ + κ² α),

with the profiles graded by the normalised depth ρ ∈ [0, 1] into the layer
(Taflove & Hagness, 3rd ed., ch. 7):

    σ = σ_max ρ^m,   κ = 1 + (κ_max − 1) ρ^m,   α = α_max (1 − ρ),
    σ_max = sigma_scale · 0.8 (m + 1) / (η0 Δ sqrt(ε_r)).

E updates take ∂/∂w of H at integer nodes, H updates take ∂/∂w of E at half
nodes, so the profiles are evaluated on both. Outside the PML b = 1, c = 0 and
1/κ = 1: ψ stays exactly zero and the update reduces exactly to plain Yee.
The upper face is the mirror image of the lower one, so a symmetric problem
stays bit-for-bit symmetric.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from etalon.constants import EPSILON_0, ETA_0, UM
from etalon.core.boundary import PML


@dataclass(frozen=True)
class CPMLAxis:
    """b, c and 1/κ along one axis: ``_e`` at integer nodes (n + 1), ``_h`` at half nodes (n)."""

    b_e: NDArray[np.float64]
    c_e: NDArray[np.float64]
    inv_kappa_e: NDArray[np.float64]
    b_h: NDArray[np.float64]
    c_h: NDArray[np.float64]
    inv_kappa_h: NDArray[np.float64]


def pml_depth(n_cells: int, layers: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Normalised depth ρ at the integer nodes (n + 1) and half nodes (n) of an axis."""
    rho_e = np.zeros(n_cells + 1)
    rho_h = np.zeros(n_cells)
    i = np.arange(layers + 1)
    rho_e[: layers + 1] = (layers - i) / layers
    i = np.arange(layers)
    rho_h[:layers] = (layers - i - 0.5) / layers
    return np.maximum(rho_e, rho_e[::-1]), np.maximum(rho_h, rho_h[::-1])


def _coefficients(
    rho: NDArray[np.float64],
    sigma_max: float,
    kappa_max: float,
    alpha_max: float,
    order: float,
    dt: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    sigma = sigma_max * rho**order
    kappa = 1.0 + (kappa_max - 1.0) * rho**order
    alpha = alpha_max * (1.0 - rho)
    b = np.exp(-(sigma / kappa + alpha) * dt / EPSILON_0)
    c = np.zeros_like(rho)
    in_pml = rho > 0.0
    s, k, a = sigma[in_pml], kappa[in_pml], alpha[in_pml]
    c[in_pml] = s * (b[in_pml] - 1.0) / (s * k + k**2 * a)
    b[~in_pml] = 1.0
    return b, c, 1.0 / kappa


def cpml_axis(
    n_cells: int,
    spacing: float,
    dt: float,
    pml: PML,
    eps_r: float,
    alpha_max: float = 0.0,
) -> CPMLAxis:
    """CPML coefficients for an axis of ``n_cells`` cells of size ``spacing`` µm.

    ``eps_r`` is the background relative permittivity (sets σ_opt); ``alpha_max``
    is the CFS shift in S/m, fixed at 0 in M0.
    """
    order = pml.grading_order
    sigma_max = pml.sigma_scale * 0.8 * (order + 1.0) / (ETA_0 * spacing * UM * math.sqrt(eps_r))
    rho_e, rho_h = pml_depth(n_cells, pml.layers)
    b_e, c_e, ik_e = _coefficients(rho_e, sigma_max, pml.kappa_max, alpha_max, order, dt)
    b_h, c_h, ik_h = _coefficients(rho_h, sigma_max, pml.kappa_max, alpha_max, order, dt)
    return CPMLAxis(b_e, c_e, ik_e, b_h, c_h, ik_h)
