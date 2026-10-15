"""Monitors: what is recorded during a run."""

from typing import Literal

from pydantic import Field, field_validator

from etalon.core.base import Coordinate, EtalonModel, FieldComponent, Size, Wavelengths


class DFTMonitor(EtalonModel):
    """Frequency-domain fields in a box, plane, line or point, from a running DFT.

        F(f) = Σ_n F(t_n) · exp(+i 2π f t_n) · Δt,      f = c / λ

    E is sampled at t_n = n Δt and H at t_n = (n + ½) Δt — the times at which
    the leapfrog scheme actually holds them. The time convention is
    exp(−iωt): a wave travelling towards +x has a phase that increases with x.
    The factor Δt makes F approximate the continuous Fourier transform, so it
    does not depend on the time step.

    Sampling: along an axis where size > 0 the monitor returns each component
    on its own Yee nodes inside [center − size/2, center + size/2], without
    interpolation; along an axis where size = 0 each component is linearly
    interpolated to the exact coordinate. A point monitor in 2D is therefore
    bilinear, and in a 2D simulation the z axis is never interpolated.

    Ref: Taflove & Hagness, 3rd ed. (DFT monitors).
    """

    type: Literal["DFTMonitor"] = Field("DFTMonitor", repr=False)
    name: str = Field(min_length=1)
    """Unique name; the key into the result (``result[name]``)."""
    center: Coordinate = (0.0, 0.0, 0.0)
    """Centre, µm."""
    size: Size = (0.0, 0.0, 0.0)
    """Extent, µm; (0, 0, 0) is a point monitor."""
    wavelengths: Wavelengths
    """Vacuum wavelengths at which to accumulate the DFT, µm."""
    components: tuple[FieldComponent, ...] | None = None
    """Components to record; None records every component the simulation computes."""

    @field_validator("components")
    @classmethod
    def _components_unique(
        cls, components: tuple[FieldComponent, ...] | None
    ) -> tuple[FieldComponent, ...] | None:
        if components is not None:
            if len(components) == 0:
                raise ValueError("components must name at least one component, or be None")
            if len(set(components)) != len(components):
                raise ValueError(f"components contains repeats: {components}")
        return components
