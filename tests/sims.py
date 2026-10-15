"""Small simulations shared by the tests."""

import numpy as np

import etalon as et


def pulse(wavelength=1.55, bandwidth=0.5, **kwargs):
    return et.GaussianPulse(wavelength=wavelength, bandwidth=bandwidth, **kwargs)


def small_sim(**overrides):
    """2 µm × 1.5 µm vacuum, 0.05 µm cells, 8-layer CPML, one Hz source, one point probe."""
    kwargs = {
        "size": (2.0, 1.5, 0.0),
        "grid": et.UniformGrid(dl=0.05),
        "boundary": et.PML(layers=8),
        "sources": [et.PointSource(center=(-0.5, 0.1, 0.0), component="Hz", pulse=pulse())],
        "monitors": [et.DFTMonitor(name="probe", center=(0.5, 0.0, 0.0), wavelengths=[1.5, 1.6])],
        "run_time": 20e-15,
        "backend": "numpy",
    }
    kwargs.update(overrides)
    return et.Simulation(**kwargs)


def wavelengths(lo, hi, n):
    return np.linspace(lo, hi, n)
