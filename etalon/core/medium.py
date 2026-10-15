"""Optical media."""

from typing import Literal

from pydantic import Field, field_validator

from etalon.core.base import EtalonModel


class Medium(EtalonModel):
    """Lossless, non-dispersive, isotropic, non-magnetic medium.

    Relative permittivity ε_r = n², relative permeability μ_r = 1
    (Taflove & Hagness, 3rd ed., ch. 3). Dispersive media (one Lorentz pole)
    arrive in M3.
    """

    type: Literal["Medium"] = Field("Medium", repr=False)
    n: float = 1.0
    """Refractive index (≥ 1)."""
    name: str | None = None
    """Label shown in summaries and in Studio."""

    @field_validator("n")
    @classmethod
    def _index_at_least_one(cls, n: float) -> float:
        if n < 1.0:
            raise ValueError(
                f"refractive index n = {n} is below 1; a lossless, non-dispersive medium "
                "with n < 1 is superluminal and makes the FDTD time step unstable"
            )
        return n

    @property
    def permittivity(self) -> float:
        """Relative permittivity ε_r = n²."""
        return self.n**2
