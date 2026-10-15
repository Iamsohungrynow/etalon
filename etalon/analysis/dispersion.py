"""Numerical dispersion of the Yee scheme, predicted and measured.

Both functions return a phase velocity normalised to the exact one, ṽp / (c/n),
so 1 means no dispersion error.
"""

import math
from typing import Literal

import numpy as np
import xarray as xr
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq
from scipy.special import hankel1

from etalon.constants import C_0_SI, UM
from etalon.grid.yee import YeeGrid2D


def numerical_phase_velocity(
    wavelengths: ArrayLike, grid: YeeGrid2D, angle: float = 0.0, n: float = 1.0
) -> NDArray[np.float64]:
    """ṽp / (c/n) of the 2D Yee scheme for vacuum wavelengths (µm) along ``angle`` (degrees).

    Solves the Yee numerical dispersion relation for k̃
    (Taflove & Hagness, 3rd ed., ch. 4; cited in the project brief as eq. 4.17),

        [ sin(ωΔt/2) / (vΔt) ]² = [ sin(k̃ cosφ Δx/2) / Δx ]² + [ sin(k̃ sinφ Δy/2) / Δy ]²,

    with v = c/n, by Newton's method from the exact k = ω/v, and returns ω/(k̃ v).
    """
    wl = np.asarray(wavelengths, dtype=np.float64) * UM
    v = C_0_SI / n
    omega = 2.0 * np.pi * C_0_SI / wl
    dt, dx, dy = grid.dt, grid.dx * UM, grid.dy * UM
    ax = math.cos(math.radians(angle)) * dx / 2.0
    ay = math.sin(math.radians(angle)) * dy / 2.0
    target = (np.sin(omega * dt / 2.0) / (v * dt)) ** 2
    k = omega / v
    for _ in range(100):
        f = (np.sin(k * ax) / dx) ** 2 + (np.sin(k * ay) / dy) ** 2 - target
        df = ax * np.sin(2.0 * k * ax) / dx**2 + ay * np.sin(2.0 * k * ay) / dy**2
        step = f / df
        k = k - step
        if np.all(np.abs(step) <= 1e-14 * k):
            return np.asarray(omega / (k * v), dtype=np.float64)
    raise ValueError(
        "Yee dispersion relation has no propagating solution for some wavelengths: "
        "they are below the grid's cut-off (too few cells per wavelength)"
    )


def _hankel_phase_correction(z: NDArray[np.float64]) -> NDArray[np.float64]:
    """arg H0⁽¹⁾(z) − (z − π/4): the near-field phase of a 2D cylindrical wave, ≈ −1/(8z)."""
    return np.asarray(np.angle(hankel1(0, z) * np.exp(-1j * (z - np.pi / 4.0))), dtype=np.float64)


def measured_phase_velocity(
    near: xr.DataArray,
    far: xr.DataArray,
    r_near: float,
    r_far: float,
    wave: Literal["cylindrical", "plane"],
    n: float = 1.0,
) -> NDArray[np.float64]:
    """ṽp / (c/n) measured from the DFT phase at two distances (µm) from a source.

    The ratio far/near cancels the source spectrum and the DFT sampling. Its phase
    is matched to k̃(r_far − r_near) for a plane wave, or, for the cylindrical wave of
    a 2D point source, to arg[H0⁽¹⁾(k̃ r_far) / H0⁽¹⁾(k̃ r_near)], which removes the
    geometric near-field phase (time convention exp(−iωt), outgoing waves H0⁽¹⁾).
    The 2π ambiguity is resolved against the exact k = 2πn/λ. Only meaningful along
    a lattice symmetry direction (0° or 45°), where rays follow the wave vector.
    """
    wavelengths = np.asarray(near["wavelength"].values, dtype=np.float64)
    if not np.array_equal(wavelengths, far["wavelength"].values):
        raise ValueError("near and far must share the same wavelengths")
    if r_far <= r_near:
        raise ValueError("r_far must be larger than r_near")
    measured = np.angle(np.asarray(far.values) / np.asarray(near.values))
    k_exact = 2.0 * np.pi * n / wavelengths  # 1/µm

    def model(k: float) -> float:
        phase = k * (r_far - r_near)
        if wave == "cylindrical":
            corr = _hankel_phase_correction(np.array([k * r_far, k * r_near]))
            phase += float(corr[0] - corr[1])
        return phase

    k_measured = np.empty_like(k_exact)
    for i, (k0, phi) in enumerate(zip(k_exact, measured, strict=True)):
        target = phi + 2.0 * np.pi * round((model(k0) - phi) / (2.0 * np.pi))
        k_measured[i] = brentq(lambda k, t=target: model(k) - t, 0.7 * k0, 1.3 * k0, xtol=1e-14)
    return k_exact / k_measured
