"""Cell-update throughput of a backend — the M0 performance criterion, and the
calibration Studio's run-time estimate will use.

Throughput = (cells incl. PML) × steps / wall time, timed after warm-up steps so
that kernel compilation and first-touch allocation are excluded.
"""

import time
from dataclasses import dataclass

import etalon as et
from etalon.fdtd.solver import FDTDSolver


@dataclass
class Throughput:
    backend: str
    device: str
    precision: str
    cells: tuple[int, int]
    """(nx, ny) including PML."""
    steps: int
    wall_time_s: float
    cell_updates_per_s: float


def measure_throughput(
    region_cells: int = 2000,
    steps: int = 500,
    backend: str = "cuda",
    precision: str = "single",
    warmup: int = 20,
) -> Throughput:
    """Time a square vacuum grid of ``region_cells``² cells plus a 12-layer CPML."""
    dl = 0.02
    sim = et.Simulation(
        size=(region_cells * dl, region_cells * dl, 0.0),
        grid=et.UniformGrid(dl=dl),
        boundary=et.PML(layers=12),
        sources=[
            et.PointSource(
                center=(0.0, 0.0, 0.0),
                component="Hz",
                pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.1),
            )
        ],
        run_time=1.0,  # not used: we step a fixed number of times
        precision=precision,
        backend=backend,
    )
    solver = FDTDSolver(sim)
    for _ in range(warmup):
        solver.step()
    solver.backend.synchronize()
    start = time.perf_counter()
    for _ in range(steps):
        solver.step()
    solver.backend.synchronize()
    wall = time.perf_counter() - start
    grid = solver.grid
    return Throughput(
        backend=solver.backend.name,
        device=solver.backend.device,
        precision=precision,
        cells=(grid.nx, grid.ny),
        steps=steps,
        wall_time_s=wall,
        cell_updates_per_s=grid.n_cells * steps / wall,
    )
