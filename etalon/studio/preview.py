"""Preview, estimate and warnings of a captured Simulation (plan-u1 §4, §13.2).

All of it is computed in the server from the validated model and the Yee grid
the solver would build (``etalon.grid``), with NumPy only: no solver state is
allocated and no GPU is touched.
"""

import math
from typing import Literal

from etalon.core.medium import Medium
from etalon.core.simulation import Simulation
from etalon.fdtd.capabilities import check_supported
from etalon.fdtd.dft import monitor_samplings
from etalon.grid.yee import TE_COMPONENTS, YeeGrid2D, build_yee_grid
from etalon.studio.contract import (
    AnyWarning,
    Background,
    Estimate,
    MemoryLargeParams,
    MemoryLargeWarning,
    MeshCoarseParams,
    MeshCoarseWarning,
    NearPmlParams,
    NearPmlWarning,
    PmlThinParams,
    PmlThinWarning,
    Preview,
    PreviewGrid,
    PreviewMedium,
    PreviewMonitor,
    PreviewPml,
    PreviewSource,
    PreviewStructure,
    Region,
    UnsupportedParams,
    UnsupportedWarning,
    Warning,
)
from etalon.studio.runner import monitor_geometry
from etalon.studio.throughput import ThroughputStore

MIN_CELLS_PER_WAVELENGTH = 20.0
NEAR_PML_CELLS = 3
MEMORY_LIMIT_BYTES = 4_000_000_000
ALL_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")
TM_COMPONENTS = frozenset({"Ez", "Hx", "Hy"})


def solver_grid(sim: Simulation) -> YeeGrid2D | None:
    """The grid the solver would build, or None where it cannot (3D until M1)."""
    try:
        return build_yee_grid(sim)
    except NotImplementedError:
        return None


def media_of(sim: Simulation) -> list[Medium]:
    """Distinct media of the structures, in order of first use."""
    media: list[Medium] = []
    for box in sim.structures:
        if box.medium not in media:
            media.append(box.medium)
    return media


def pml_thickness(sim: Simulation, grid: YeeGrid2D | None) -> tuple[float, float, float]:
    """PML thickness on the faces of each axis, µm (0 along a flat axis)."""
    layers = sim.boundary.layers
    if grid is not None:
        return layers * grid.dx, layers * grid.dy, 0.0

    def cell(size: float) -> float:  # UniformGrid: N = ceil(size / dl) cells of size / N
        return size / math.ceil(round(size / sim.grid.dl, 9)) if size > 0 else 0.0

    x, y, z = (layers * cell(size) for size in sim.size)
    return x, y, z


def build_preview(sim: Simulation, grid: YeeGrid2D | None) -> Preview:
    media = media_of(sim)
    layers = sim.boundary.layers
    default_components = TE_COMPONENTS if sim.is_2d else ALL_COMPONENTS
    return Preview(
        is_2d=sim.is_2d,
        plane_z=sim.center[2],
        region=Region(center=sim.center, size=sim.size),
        pml=PreviewPml(layers=layers, thickness=pml_thickness(sim, grid)),
        background=Background(n=sim.medium.n, name=sim.medium.name),
        media=[
            PreviewMedium(id=f"medium:{i}", name=medium.name, n=medium.n)
            for i, medium in enumerate(media)
        ],
        structures=[
            PreviewStructure(
                id=f"structure:{i}",
                name=box.name,
                kind="Box",
                center=box.center,
                size=box.size,
                medium_id=f"medium:{media.index(box.medium)}",
            )
            for i, box in enumerate(sim.structures)
        ],
        sources=[
            PreviewSource(
                id=f"source:{i}",
                name=source.name,
                kind="PointSource",
                center=source.center,
                component=source.component,
                wavelength_um=source.pulse.wavelength,
                bandwidth_um=source.pulse.bandwidth,
            )
            for i, source in enumerate(sim.sources)
        ],
        monitors=[
            PreviewMonitor(
                id=f"monitor:{monitor.name}",
                name=monitor.name,
                kind="DFTMonitor",
                geometry=monitor_geometry(monitor.size),
                center=monitor.center,
                size=monitor.size,
                wavelengths_um=list(monitor.wavelengths),
                components=list(monitor.components or default_components),
            )
            for monitor in sim.monitors
        ],
        grid=None
        if grid is None
        else PreviewGrid(
            dx=grid.dx,
            dy=grid.dy,
            nx=grid.nx,
            ny=grid.ny,
            region_cells=grid.region_cells,
            dt_s=grid.dt,
            courant=grid.courant,
            steps=grid.n_steps(sim.run_time),
        ),
    )


def is_supported(sim: Simulation) -> bool:
    try:
        check_supported(sim)
    except NotImplementedError:
        return False
    return True


def memory_bytes(sim: Simulation, grid: YeeGrid2D) -> int:
    """Device memory of a 2D TE run: what ``Simulation.summary()`` reports, in bytes.

    Three arrays per component (field, CPML ψ, coefficient: Ex, ψ_Ex,y, Δt/ε at Ex;
    Ey, ψ_Ey,x, Δt/ε at Ey; Hz, ψ_Hz,x, ψ_Hz,y) and one complex accumulator per
    monitor node and wavelength.
    """
    real_bytes = 4 if sim.precision == "single" else 8
    nodes = sum(n_x * n_y for n_x, n_y in map(grid.shape, TE_COMPONENTS))
    total = 3 * nodes * real_bytes
    if is_supported(sim):
        for monitor in sim.monitors:
            for sampling in monitor_samplings(monitor, grid):
                total += 2 * real_bytes * sampling.flat_index.size * sampling.wavelengths.size
    return total


def run_backend(settings_backend: str, sim_backend: str, has_gpu: bool) -> str:
    """``cpu`` or ``cuda:N``: the backend a Studio run of this script will use."""
    if settings_backend == "cpu":
        return "cpu"
    if settings_backend.startswith("cuda:"):
        return settings_backend
    if sim_backend == "numpy":
        return "cpu"
    if sim_backend == "cuda":
        return "cuda:0"
    return "cuda:0" if has_gpu else "cpu"


def build_estimate(
    sim: Simulation, grid: YeeGrid2D, throughput: ThroughputStore, backend: str
) -> Estimate:
    cells = grid.n_cells
    steps = grid.n_steps(sim.run_time)
    found = throughput.lookup(backend)
    basis: Literal["measured", "calibration", "unknown"] = "unknown"
    cells_per_s = seconds = None
    if found is not None:
        basis, cells_per_s = found
        seconds = cells * steps / cells_per_s
    return Estimate(
        cells=cells,
        memory_bytes=memory_bytes(sim, grid),
        steps=steps,
        dt_s=grid.dt,
        run_time_s=sim.run_time,
        seconds=seconds,
        cells_per_s=cells_per_s,
        basis=basis,
    )


def _unsupported(sim: Simulation) -> list[AnyWarning]:
    if is_supported(sim):
        return []
    found: list[AnyWarning] = []

    def add(feature: Literal["3d", "tm"], object_id: str | None) -> None:
        params = UnsupportedParams(feature=feature, milestone="M1")
        found.append(
            UnsupportedWarning(
                code="unsupported", severity="error", object_id=object_id, params=params
            )
        )

    if not sim.is_2d:
        add("3d", None)
    else:
        for i, source in enumerate(sim.sources):
            if source.component in TM_COMPONENTS:
                add("tm", f"source:{i}")
        for monitor in sim.monitors:
            if TM_COMPONENTS & set(monitor.components or ()):
                add("tm", f"monitor:{monitor.name}")
    if not found:
        add("3d" if not sim.is_2d else "tm", None)
    return found


def _shortest_wavelength(sim: Simulation) -> float:
    """Shortest vacuum wavelength of interest: source band edges and monitor wavelengths."""
    candidates = [s.pulse.wavelength - s.pulse.bandwidth / 2.0 for s in sim.sources]
    for monitor in sim.monitors:
        candidates.extend(monitor.wavelengths)
    return min(candidates)


def _cells_to_pml(lo: float, hi: float, region_lo: float, region_hi: float, d: float) -> int:
    gap = min(lo - region_lo, region_hi - hi)
    return max(0, math.floor(gap / d + 1e-6))


def build_warnings(sim: Simulation, grid: YeeGrid2D | None, memory: int | None) -> list[Warning]:
    """Every warning of plan-u1 §4 that applies; codes and numbers only, no prose."""
    found = _unsupported(sim)
    if grid is not None:
        found += _grid_warnings(sim, grid)
    if memory is not None and memory > MEMORY_LIMIT_BYTES:
        found.append(
            MemoryLargeWarning(
                code="memory_large",
                severity="warning",
                object_id="grid",
                params=MemoryLargeParams(bytes=memory),
            )
        )
    return [Warning(item) for item in found]


def _grid_warnings(sim: Simulation, grid: YeeGrid2D) -> list[AnyWarning]:
    found: list[AnyWarning] = []
    densest = max([sim.medium, *media_of(sim)], key=lambda medium: medium.n)
    wavelength = _shortest_wavelength(sim)
    per_wavelength = wavelength / (densest.n * max(grid.dx, grid.dy))
    if per_wavelength < MIN_CELLS_PER_WAVELENGTH:
        found.append(
            MeshCoarseWarning(
                code="mesh_coarse",
                severity="warning",
                object_id="grid",
                params=MeshCoarseParams(
                    cells_per_wavelength=per_wavelength,
                    minimum=MIN_CELLS_PER_WAVELENGTH,
                    medium=densest.name,
                    wavelength_um=wavelength,
                ),
            )
        )
    thickness = sim.boundary.layers * min(grid.dx, grid.dy)
    longest = max(source.pulse.wavelength for source in sim.sources)
    half = longest / sim.medium.n / 2.0
    if thickness < half:
        found.append(
            PmlThinWarning(
                code="pml_thin",
                severity="warning",
                object_id="boundary",
                params=PmlThinParams(thickness_um=thickness, half_wavelength_um=half),
            )
        )
    boxes: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = [
        (f"source:{i}", source.center, (0.0, 0.0, 0.0)) for i, source in enumerate(sim.sources)
    ]
    boxes += [(f"monitor:{m.name}", m.center, m.size) for m in sim.monitors]
    for object_id, center, size in boxes:
        cells = min(
            _cells_to_pml(
                center[axis] - size[axis] / 2.0,
                center[axis] + size[axis] / 2.0,
                sim.center[axis] - sim.size[axis] / 2.0,
                sim.center[axis] + sim.size[axis] / 2.0,
                (grid.dx, grid.dy)[axis],
            )
            for axis in (0, 1)
        )
        if cells < NEAR_PML_CELLS:
            found.append(
                NearPmlWarning(
                    code="near_pml",
                    severity="warning",
                    object_id=object_id,
                    params=NearPmlParams(cells=cells),
                )
            )
    return found
