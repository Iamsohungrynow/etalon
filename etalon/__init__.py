"""etalon — photonic FDTD on one local GPU, with a Python-native API.

Lengths are in micrometres, time in seconds, frequency in hertz.

Every public name loads on first use (PEP 562 module ``__getattr__``), so
``import etalon`` itself imports nothing: ``etalon.analysis`` and
``etalon.SimulationResult`` pull in SciPy and xarray (seconds), and the models
NumPy and pydantic (about 0.5 s), which ``etalon studio`` does not need to start
(docs/plan-u1.md §14.1). ``et.Simulation`` and the rest work as before.
"""

import importlib
from typing import TYPE_CHECKING, Any

__version__ = "0.0.1"

if TYPE_CHECKING:
    from etalon import analysis
    from etalon.constants import C_0, freq_to_wvl, wvl_to_freq
    from etalon.core.boundary import PML
    from etalon.core.grid_spec import UniformGrid
    from etalon.core.medium import Medium
    from etalon.core.monitor import DFTMonitor
    from etalon.core.simulation import Simulation
    from etalon.core.source import GaussianPulse, PointSource
    from etalon.geometry.box import Box
    from etalon.io.result import SimulationResult

_LAZY = {
    # name -> the module that defines it
    "C_0": "etalon.constants",
    "freq_to_wvl": "etalon.constants",
    "wvl_to_freq": "etalon.constants",
    "PML": "etalon.core.boundary",
    "UniformGrid": "etalon.core.grid_spec",
    "Medium": "etalon.core.medium",
    "DFTMonitor": "etalon.core.monitor",
    "Simulation": "etalon.core.simulation",
    "GaussianPulse": "etalon.core.source",
    "PointSource": "etalon.core.source",
    "Box": "etalon.geometry.box",
    "SimulationResult": "etalon.io.result",
}

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
    """Import a public name the first time it is used, then keep it as a plain attribute."""
    if name == "analysis":
        # Importing a submodule also binds it as an attribute of this package.
        return importlib.import_module("etalon.analysis")
    if name in _LAZY:
        value = getattr(importlib.import_module(_LAZY[name]), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'etalon' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
