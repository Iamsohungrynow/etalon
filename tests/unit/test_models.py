"""Model tests: construction, validation messages, JSON round trip (plan-m0 U1, U2)."""

import math

import numpy as np
import pytest
from pydantic import ValidationError

import etalon as et


def pulse(**overrides):
    kwargs = {"wavelength": 1.55, "bandwidth": 0.5}
    kwargs.update(overrides)
    return et.GaussianPulse(**kwargs)


def vacuum_sim(**overrides):
    """The simulation from examples/00_vacuum_pulse.py."""
    wavelengths = np.linspace(1.30, 1.80, 26)
    kwargs = {
        "size": (8.0, 8.0, 0.0),
        "grid": et.UniformGrid(dl=0.05),
        "boundary": et.PML(layers=12),
        "sources": [et.PointSource(center=(-3.0, 0.0, 0.0), component="Hz", pulse=pulse())],
        "monitors": [
            et.DFTMonitor(name="near", center=(-1.0, 0.0, 0.0), wavelengths=wavelengths),
            et.DFTMonitor(name="far", center=(3.0, 0.0, 0.0), wavelengths=wavelengths),
            et.DFTMonitor(name="field", size=(8.0, 8.0, 0.0), wavelengths=[1.55]),
        ],
        "run_time": 300e-15,
    }
    kwargs.update(overrides)
    return et.Simulation(**kwargs)


def test_constants():
    assert et.C_0 == 299_792_458.0e6
    assert et.wvl_to_freq(1.55) == pytest.approx(193.414e12, rel=1e-5)
    assert et.freq_to_wvl(et.wvl_to_freq(1.31)) == pytest.approx(1.31, rel=1e-15)
    wavelengths = np.array([1.5, 1.6])
    np.testing.assert_allclose(et.freq_to_wvl(et.wvl_to_freq(wavelengths)), wavelengths)


def test_example_simulation_builds():
    sim = vacuum_sim()
    assert sim.is_2d
    assert sim.medium.n == 1.0
    assert sim.courant == 0.99
    assert sim.precision == "single"
    assert sim.backend == "auto"
    assert isinstance(sim.monitors[0].wavelengths, tuple)
    assert sim.monitors[0].wavelengths[0] == 1.3


def test_json_round_trip():
    si = et.Medium(n=3.476, name="si")
    sim = vacuum_sim(
        structures=[et.Box(center=(1.0, 0.0, 0.0), size=(2.0, 0.5, 0.22), medium=si)],
        precision="double",
    )
    again = et.Simulation.model_validate_json(sim.model_dump_json())
    assert again == sim
    assert '"type":"Box"' in sim.model_dump_json()


def test_models_are_frozen_and_hashable():
    sim = vacuum_sim()
    with pytest.raises(ValidationError, match="frozen"):
        sim.run_time = 1e-12
    assert hash(sim) == hash(vacuum_sim())


def test_unknown_keyword_is_an_error():
    with pytest.raises(ValidationError, match="wavelenght"):
        et.GaussianPulse(wavelength=1.55, bandwidth=0.1, wavelenght=1.5)


def test_numpy_inputs_are_accepted():
    source = et.PointSource(
        center=np.array([0.5, -0.25, 0.0]), component="Ey", pulse=pulse(wavelength=np.float64(1.31))
    )
    assert source.center == (0.5, -0.25, 0.0)
    assert source.pulse.wavelength == 1.31


def test_nan_and_inf_are_rejected():
    with pytest.raises(ValidationError):
        pulse(wavelength=math.nan)
    with pytest.raises(ValidationError):
        et.Box(size=(math.inf, 1.0, 1.0), medium=et.Medium())


def test_medium_index_below_one():
    with pytest.raises(ValidationError, match=r"n = 0\.9 is below 1"):
        et.Medium(n=0.9)
    assert et.Medium(n=1.5).permittivity == pytest.approx(2.25)


def test_courant_range():
    assert vacuum_sim(courant=1.0).courant == 1.0
    for bad in (0.0, 1.01):
        with pytest.raises(ValidationError, match="courant"):
            vacuum_sim(courant=bad)


def test_pulse_band_must_stay_positive():
    with pytest.raises(ValidationError, match="smaller than 2 × wavelength"):
        pulse(bandwidth=3.1)


def test_pulse_derived_quantities():
    p = pulse()
    f_hi = et.C_0 / 1.30
    f_lo = et.C_0 / 1.80
    assert p.frequency == pytest.approx(et.C_0 / 1.55)
    assert p.frequency_width == pytest.approx((f_hi - f_lo) / 2)
    assert p.width == pytest.approx(1 / (2 * math.pi * p.frequency_width))
    assert p.delay == pytest.approx(5 * p.width)
    assert 4e-15 < p.width < 6e-15  # ~5 fs for a 0.5 µm band at 1.55 µm


def test_needs_a_source():
    with pytest.raises(ValidationError, match="sources"):
        vacuum_sim(sources=[])


def test_xy_size_must_be_positive():
    with pytest.raises(ValidationError, match="size_x and size_y must be > 0"):
        vacuum_sim(size=(0.0, 8.0, 0.0))


def test_monitor_names_unique():
    m = et.DFTMonitor(name="probe", wavelengths=[1.55])
    with pytest.raises(ValidationError, match="repeated: probe"):
        vacuum_sim(monitors=[m, m])


def test_monitor_components_unique():
    with pytest.raises(ValidationError, match="repeats"):
        et.DFTMonitor(name="probe", wavelengths=[1.55], components=("Hz", "Hz"))


def test_source_outside_region():
    src = et.PointSource(center=(4.5, 0.0, 0.0), component="Hz", pulse=pulse())
    with pytest.raises(ValidationError, match=r"source 'sources\[0\]' spans x"):
        vacuum_sim(sources=[src])


def test_source_on_region_edge_is_inside():
    src = et.PointSource(center=(4.0, -4.0, 0.0), component="Hz", pulse=pulse())
    vacuum_sim(sources=[src])


def test_2d_sources_and_monitors_must_be_in_plane():
    src = et.PointSource(center=(0.0, 0.0, 0.1), component="Hz", pulse=pulse(), name="dipole")
    with pytest.raises(ValidationError, match="'dipole' must lie in the simulation plane z = 0"):
        vacuum_sim(sources=[src])
    thick = et.DFTMonitor(name="thick", size=(1.0, 1.0, 0.5), wavelengths=[1.55])
    with pytest.raises(ValidationError, match="'thick' must lie in the simulation plane"):
        vacuum_sim(monitors=[thick])


def test_monitor_larger_than_region():
    big = et.DFTMonitor(name="big", size=(9.0, 8.0, 0.0), wavelengths=[1.55])
    with pytest.raises(ValidationError, match="'big' spans x"):
        vacuum_sim(monitors=[big])


def test_run_is_not_wired_yet():
    with pytest.raises(NotImplementedError):
        vacuum_sim().run()
