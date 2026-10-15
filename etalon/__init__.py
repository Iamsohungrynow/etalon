"""etalon — photonic FDTD on one local GPU, with a Python-native API.

Lengths are in micrometres, time in seconds, frequency in hertz.
"""

from etalon.constants import C_0, freq_to_wvl, wvl_to_freq
from etalon.core.boundary import PML
from etalon.core.grid_spec import UniformGrid
from etalon.core.medium import Medium
from etalon.core.monitor import DFTMonitor
from etalon.core.simulation import Simulation
from etalon.core.source import GaussianPulse, PointSource
from etalon.geometry.box import Box

__version__ = "0.0.1"

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
