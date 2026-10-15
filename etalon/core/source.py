"""Sources: what drives the fields, and with which time signature."""

import math
from typing import Literal

from pydantic import Field, PositiveFloat, model_validator

from etalon.constants import C_0
from etalon.core.base import Coordinate, EtalonModel, FieldComponent


class GaussianPulse(EtalonModel):
    """Sine-modulated Gaussian pulse: the time signature of a broadband source.

        g(t) = amplitude · exp(−(t − t0)² / (2τ²)) · sin(2π f0 (t − t0))

    with f0 = c / wavelength. The wavelength band
    [wavelength − bandwidth/2, wavelength + bandwidth/2] maps to frequencies
    [f_lo, f_hi]; the spectral standard deviation is σ_f = (f_hi − f_lo) / 2,
    so the band edges sit about one σ_f from the peak (spectral amplitude
    ≈ e^(−1/2) ≈ 0.61 of the peak). τ = 1 / (2π σ_f) is the matching temporal
    width and t0 = 5τ, so the pulse switches on smoothly (g(0) ≈ 4e-6 of peak).

    The sine (odd) modulation makes the pulse exactly zero-mean, ∫ g dt = 0,
    so a current source driven by it leaves no static charge behind however
    wide the band is.

    Ref: Taflove & Hagness, 3rd ed., ch. 5 (pulsed source waveforms).
    """

    type: Literal["GaussianPulse"] = Field("GaussianPulse", repr=False)
    wavelength: PositiveFloat
    """Centre vacuum wavelength, µm."""
    bandwidth: PositiveFloat
    """Full width of the wavelength band, µm (must be < 2 × wavelength)."""
    amplitude: float = 1.0
    """Scale factor on the injected current (see PointSource for units)."""

    @model_validator(mode="after")
    def _band_stays_positive(self) -> "GaussianPulse":
        if self.bandwidth >= 2.0 * self.wavelength:
            raise ValueError(
                f"bandwidth {self.bandwidth} µm must be smaller than 2 × wavelength "
                f"({2.0 * self.wavelength} µm), otherwise the band reaches λ ≤ 0"
            )
        return self

    @property
    def frequency(self) -> float:
        """Centre frequency f0 = c / wavelength, Hz."""
        return C_0 / self.wavelength

    @property
    def frequency_width(self) -> float:
        """Spectral standard deviation σ_f = (f_hi − f_lo) / 2, Hz."""
        f_hi = C_0 / (self.wavelength - self.bandwidth / 2.0)
        f_lo = C_0 / (self.wavelength + self.bandwidth / 2.0)
        return (f_hi - f_lo) / 2.0

    @property
    def width(self) -> float:
        """Temporal standard deviation τ = 1 / (2π σ_f), s."""
        return 1.0 / (2.0 * math.pi * self.frequency_width)

    @property
    def delay(self) -> float:
        """Time of the envelope peak, t0 = 5τ, s."""
        return 5.0 * self.width


class PointSource(EtalonModel):
    """Point dipole: an electric (Ex, Ey, Ez) or magnetic (Hx, Hy, Hz) current.

    In a 2D simulation it is a line source along z. The current is shared
    between the nearest Yee nodes of its component with bilinear weights that
    sum to 1, so an off-grid position is not snapped to the grid. The injected
    current density is

        J = amplitude · g(t) / (Δx Δy)          (2D)

    — a line dipole whose strength does not depend on the cell size, so the
    radiated field converges as the grid is refined. Magnetic components inject
    a magnetic current density M the same way (∇×E = −μ ∂H/∂t − M).

    In M0, 2D simulations are TE (Ex, Ey, Hz); Ez, Hx and Hy are rejected when
    the simulation is run.
    """

    type: Literal["PointSource"] = Field("PointSource", repr=False)
    center: Coordinate
    """Position, µm."""
    component: FieldComponent
    """Which current component is driven."""
    pulse: GaussianPulse
    """Time signature."""
    name: str | None = None
    """Label shown in summaries and in Studio."""
