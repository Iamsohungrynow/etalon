"""Physical constants and unit conversions.

The public API measures length in micrometres (µm), time in seconds and
frequency in hertz; the solver internals are SI. Values are CODATA 2018
(c exact; μ0 = 1.25663706212e-6 H/m).
"""

from typing import TypeVar

import numpy as np
from numpy.typing import NDArray

C_0_SI: float = 299_792_458.0
"""Speed of light in vacuum, m/s (exact)."""

C_0: float = C_0_SI * 1e6
"""Speed of light in vacuum in API units, µm/s."""

MU_0: float = 1.25663706212e-6
"""Vacuum permeability, H/m."""

EPSILON_0: float = 1.0 / (MU_0 * C_0_SI**2)
"""Vacuum permittivity, F/m: ε0 = 1 / (μ0 c²)."""

ETA_0: float = MU_0 * C_0_SI
"""Impedance of free space, Ω: η0 = μ0 c."""

UM: float = 1e-6
"""Metres per micrometre: SI length = API length · UM."""

FloatOrArray = TypeVar("FloatOrArray", float, NDArray[np.float64])


def wvl_to_freq(wavelength: FloatOrArray) -> FloatOrArray:
    """Frequency in Hz of a vacuum wavelength in µm: f = c / λ."""
    return C_0 / wavelength


def freq_to_wvl(frequency: FloatOrArray) -> FloatOrArray:
    """Vacuum wavelength in µm of a frequency in Hz: λ = c / f."""
    return C_0 / frequency
