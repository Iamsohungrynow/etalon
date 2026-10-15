"""Axis-aligned box."""

from typing import Literal

from pydantic import Field

from etalon.core.base import Coordinate, EtalonModel, Size
from etalon.core.medium import Medium


class Box(EtalonModel):
    """Axis-aligned rectangular block filled with one medium.

    Where structures overlap, the one later in ``Simulation.structures`` wins.
    Structures may extend beyond the simulation region; the PML then sees them.
    In a 2D simulation the box takes part when the simulation plane
    z = Simulation.center_z lies within [center_z − size_z/2, center_z + size_z/2]
    (ends included).

    M0 gives each Yee node the medium at that node (staircasing); subpixel
    smoothing (Farjadpour et al., Opt. Lett. 31, 2972 (2006)) arrives in M1.
    """

    type: Literal["Box"] = Field("Box", repr=False)
    center: Coordinate = (0.0, 0.0, 0.0)
    """Centre, µm."""
    size: Size
    """Extent, µm."""
    medium: Medium
    """Material inside the box."""
    name: str | None = None
    """Label shown in summaries and in Studio."""
