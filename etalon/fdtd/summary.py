"""Simulation.summary(): what a run will cost, before it starts.

The text is plain ASCII ("um", "dt") so printing it never fails on a console
whose encoding lacks µ or Δ (cp1252 pipes, GBK on Chinese Windows).
"""

from etalon import __version__
from etalon.core.simulation import Simulation
from etalon.fdtd.capabilities import check_supported
from etalon.fdtd.dft import monitor_samplings
from etalon.grid.yee import build_yee_grid


def summary(sim: Simulation) -> str:
    """Cells, cell size, time step, number of steps and memory of a simulation."""
    check_supported(sim)
    grid = build_yee_grid(sim)
    real_bytes = 4 if sim.precision == "single" else 8
    # Three arrays per component: Ex + psi_Ex,y + dt/eps at Ex; Ey + psi_Ey,x + dt/eps at Ey;
    # Hz + psi_Hz,x + psi_Hz,y (psi arrays are full size in M0).
    nodes = sum(n_x * n_y for n_x, n_y in map(grid.shape, ("Ex", "Ey", "Hz")))
    field_bytes = 3 * nodes * real_bytes
    monitor_bytes = 0
    for monitor in sim.monitors:
        for sampling in monitor_samplings(monitor, grid):
            monitor_bytes += 2 * real_bytes * sampling.flat_index.size * sampling.wavelengths.size
    region_x, region_y = grid.region_cells
    steps = grid.n_steps(sim.run_time)
    return "\n".join(
        [
            f"etalon {__version__} | 2D TE (Ex, Ey, Hz) | backend {sim.backend}, "
            f"{sim.precision} precision",
            f"grid    {grid.nx} x {grid.ny} cells = {region_x} x {region_y} region "
            f"+ {grid.pml_layers}-cell CPML per face; dx = {grid.dx:.4g} um, dy = {grid.dy:.4g} um",
            f"time    dt = {grid.dt:.5g} s (courant {grid.courant}); {steps} steps "
            f"for {sim.run_time * 1e15:.4g} fs",
            f"memory  {field_bytes / 1e6:.3g} MB fields + {monitor_bytes / 1e6:.3g} MB monitors",
        ]
    )
