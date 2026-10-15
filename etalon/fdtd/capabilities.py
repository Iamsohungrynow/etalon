"""What this build of the solver can run. Each refusal names the milestone that adds it."""

from etalon.core.simulation import Simulation
from etalon.grid.yee import TE_COMPONENTS


def check_supported(sim: Simulation) -> None:
    """Raise NotImplementedError for a valid description the solver cannot run yet."""
    if not sim.is_2d:
        raise NotImplementedError("3D simulations arrive in M1; set size_z = 0 for a 2D simulation")
    for i, source in enumerate(sim.sources):
        if source.component not in TE_COMPONENTS:
            label = source.name or f"sources[{i}]"
            raise NotImplementedError(
                f"source {label!r} drives {source.component}, a 2D TM component; this build "
                "simulates 2D TE only (Ex, Ey, Hz)"
            )
    for monitor in sim.monitors:
        for component in monitor.components or ():
            if component not in TE_COMPONENTS:
                raise NotImplementedError(
                    f"monitor {monitor.name!r} asks for {component}, a 2D TM component; this "
                    "build simulates 2D TE only (Ex, Ey, Hz)"
                )
