"""The Simulation model: everything that defines one FDTD run."""

from typing import Literal

from pydantic import Field, PositiveFloat, model_validator

from etalon.core.base import Coordinate, EtalonModel, Size
from etalon.core.boundary import PML
from etalon.core.grid_spec import UniformGrid
from etalon.core.medium import Medium
from etalon.core.monitor import DFTMonitor
from etalon.core.source import PointSource
from etalon.geometry.box import Box


class Simulation(EtalonModel):
    """One FDTD simulation: region, materials, grid, boundaries, sources, monitors.

    The simulation region is the box ``center ± size/2`` (µm). A zero
    ``size_z`` makes the simulation 2D: fields are invariant along z and the
    plane z = center_z is simulated. PML layers are added outside the region,
    so everything inside it is physical domain.

    The time step follows from the grid and the Courant factor
    (Taflove & Hagness, 3rd ed., ch. 4, Courant stability limit):

        Δt = courant / (c · sqrt(1/Δx² + 1/Δy² [+ 1/Δz²]))

    so courant = 1 is the stability limit. This is Lumerical's "dt stability
    factor"; Meep's Courant number S corresponds to courant = S · sqrt(D) in a
    D-dimensional simulation.

    The model checks that the description is self-consistent (sources and
    monitors inside the region, unique monitor names, ...). Whether the solver
    supports it yet (3D, 2D TM) is checked when it is run.
    """

    center: Coordinate = (0.0, 0.0, 0.0)
    """Centre of the simulation region, µm."""
    size: Size
    """Extent of the simulation region, µm, PML excluded; size_z = 0 means 2D."""
    medium: Medium = Medium()
    """Background medium filling everything not covered by a structure."""
    structures: tuple[Box, ...] = ()
    """Structures, later ones winning where they overlap."""
    grid: UniformGrid
    """Mesh specification."""
    boundary: PML = PML()
    """Boundary on every face of an axis with non-zero size."""
    sources: tuple[PointSource, ...] = Field(min_length=1)
    """At least one source."""
    monitors: tuple[DFTMonitor, ...] = ()
    """Monitors; their names must be unique."""
    run_time: PositiveFloat
    """Simulated time, s."""
    courant: float = Field(0.99, gt=0.0, le=1.0)
    """Time step as a fraction of the Courant stability limit."""
    precision: Literal["single", "double"] = "single"
    """float32 fields and complex64 DFT accumulators, or float64 / complex128."""
    backend: Literal["auto", "numpy", "cuda"] = "auto"
    """"cuda" fails loudly without a GPU; "auto" uses one if CuPy finds it, else NumPy."""

    @property
    def is_2d(self) -> bool:
        """True when size_z = 0: a z-invariant 2D simulation."""
        return self.size[2] == 0.0

    @model_validator(mode="after")
    def _check_layout(self) -> "Simulation":
        if self.size[0] == 0.0 or self.size[1] == 0.0:
            raise ValueError(
                f"size = {self.size}: size_x and size_y must be > 0 "
                "(set size_z = 0 for a 2D simulation)"
            )
        names = [monitor.name for monitor in self.monitors]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(f"monitor names must be unique; repeated: {', '.join(repeated)}")
        for i, source in enumerate(self.sources):
            label = source.name or f"sources[{i}]"
            self._check_inside(f"source {label!r}", source.center, (0.0, 0.0, 0.0))
        for monitor in self.monitors:
            self._check_inside(f"monitor {monitor.name!r}", monitor.center, monitor.size)
        return self

    def _check_inside(
        self,
        what: str,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
    ) -> None:
        """Raise if the box center ± size/2 is not inside the simulation region."""
        for axis, c, s, region_c, region_s in zip(
            "xyz", center, size, self.center, self.size, strict=True
        ):
            lo, hi = c - s / 2.0, c + s / 2.0
            region_lo, region_hi = region_c - region_s / 2.0, region_c + region_s / 2.0
            tol = 1e-9 * max(1.0, abs(region_lo), abs(region_hi))
            if lo >= region_lo - tol and hi <= region_hi + tol:
                continue
            if axis == "z" and region_s == 0.0:
                raise ValueError(
                    f"{what} must lie in the simulation plane z = {region_c} µm "
                    "with size_z = 0 (this is a 2D simulation)"
                )
            raise ValueError(
                f"{what} spans {axis} = [{lo}, {hi}] µm, outside the simulation region "
                f"{axis} = [{region_lo}, {region_hi}] µm; sources and monitors must be inside "
                "the region (the PML is outside it)"
            )

    def summary(self) -> str:
        """Cells, time step, number of steps and memory, before anything runs."""
        raise NotImplementedError("Simulation.summary() is implemented in M0 step 3")

    def run(self) -> object:
        """Run the simulation; returns an ``etalon.SimulationResult``."""
        raise NotImplementedError("Simulation.run() is implemented in M0 step 3")
