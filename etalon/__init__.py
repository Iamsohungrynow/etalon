"""etalon — photonic FDTD on one local GPU, with a Python-native API.

Lengths are in micrometres, time in seconds, frequency in hertz.

``etalon.analysis`` and ``etalon.SimulationResult`` load on first use (PEP 562
module ``__getattr__``): they import SciPy and xarray, which take seconds, and
neither building a ``Simulation`` nor starting ``etalon studio`` needs them.
"""

import importlib
from typing import TYPE_CHECKING, Any

from etalon.constants import C_0, freq_to_wvl, wvl_to_freq
from etalon.core.boundary import PML
from etalon.core.grid_spec import UniformGrid
from etalon.core.medium import Medium
from etalon.core.monitor import DFTMonitor
from etalon.core.simulation import Simulation
from etalon.core.source import GaussianPulse, PointSource
from etalon.geometry.box import Box

__version__ = "0.0.1"

if TYPE_CHECKING:
    from etalon import analysis
    from etalon.io.result import SimulationResult

__all__ = [
    "C_0",
    "PML",
    "Box",
    "DFTMonitor",
    "GaussianPulse",
    "Medium",
    "PointSource",
    "Simulation",
    "SimulationResult",
    "UniformGrid",
    "__version__",
    "analysis",
    "freq_to_wvl",
    "wvl_to_freq",
]


def __getattr__(name: str) -> Any:
    """Import ``analysis`` and ``SimulationResult`` the first time they are used."""
    if name == "analysis":
        # Importing a submodule also binds it as an attribute of this package.
        return importlib.import_module("etalon.analysis")
    if name == "SimulationResult":
        result_class = importlib.import_module("etalon.io.result").SimulationResult
        globals()["SimulationResult"] = result_class
        return result_class
    raise AttributeError(f"module 'etalon' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | {"analysis", "SimulationResult"})
