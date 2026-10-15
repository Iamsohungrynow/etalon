"""Grid specifications: how the user asks for a mesh.

The computed Yee grid (node coordinates, Δt) lives in ``etalon.grid``.
"""

from typing import Literal

from pydantic import Field, PositiveFloat

from etalon.core.base import EtalonModel


class UniformGrid(EtalonModel):
    """Uniform Yee grid whose cells are no larger than ``dl`` along any axis.

    Each axis with non-zero size gets N = ceil(size / dl) cells of
    Δ = size / N, so the region edges stay exactly where they were put and the
    mesh is never coarser than asked (Δ ≤ dl). When size is a multiple of dl,
    Δ = dl exactly. Field components sit on the staggered Yee lattice
    (Taflove & Hagness, 3rd ed., ch. 3).
    """

    type: Literal["UniformGrid"] = Field("UniformGrid", repr=False)
    dl: PositiveFloat
    """Largest allowed cell size, µm."""
