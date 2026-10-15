"""Boundary conditions."""

from typing import Literal

from pydantic import Field

from etalon.core.base import EtalonModel


class PML(EtalonModel):
    """Convolutional perfectly matched layer (CPML) on every face of the region.

    Applied to both faces of every axis with non-zero size (in 2D: x and y).
    The layers are added outside ``Simulation.size`` — as in Lumerical and
    Tidy3D, and unlike Meep, where the PML sits inside the cell.

    Complex-frequency-shifted stretching s_w = κ_w + σ_w / (α_w + iωε0), applied
    by recursive convolution (Roden & Gedney 2000):

        ψ^(n+1) = b ψ^n + c ∂_w F
        b = exp(−(σ/κ + α) Δt / ε0),   c = σ (b − 1) / (σ κ + κ² α)

    and the spatial derivative ∂_w F in the update becomes (1/κ) ∂_w F + ψ.
    The profiles are graded with the normalised depth ρ ∈ [0, 1] into the layer
    (Taflove & Hagness, 3rd ed., ch. 7):

        σ(ρ) = σ_max ρ^m,   κ(ρ) = 1 + (κ_max − 1) ρ^m,   α(ρ) = α_max (1 − ρ)
        σ_max = sigma_scale · 0.8 (m + 1) / (η0 Δ sqrt(ε_r))

    M0 fixes α_max = 0; the kernels already carry α, and it becomes a setting
    in M1 once its units are agreed.
    """

    type: Literal["PML"] = Field("PML", repr=False)
    layers: int = Field(12, ge=1)
    """Number of PML cells on each face."""
    grading_order: float = Field(3.0, ge=1.0, le=6.0)
    """Polynomial order m of the σ and κ profiles."""
    sigma_scale: float = Field(1.0, gt=0.0)
    """σ_max as a multiple of σ_opt = 0.8 (m + 1) / (η0 Δ sqrt(ε_r))."""
    kappa_max: float = Field(1.0, ge=1.0)
    """κ at the outer face; κ > 1 helps absorb evanescent fields."""
