"""Capability errors, backend selection and result layout (plan-m0 U11, U12)."""

import sys

import numpy as np
import pytest

import etalon as et
from etalon.fdtd.backends import get_backend
from etalon.fdtd.backends.numpy_backend import NumpyBackend
from tests.sims import pulse, small_sim


def test_tm_source_is_refused():
    src = et.PointSource(center=(0, 0, 0), component="Ez", pulse=pulse(), name="tm")
    with pytest.raises(NotImplementedError, match=r"'tm' drives Ez.*2D TE only"):
        small_sim(sources=[src]).run()


def test_tm_monitor_component_is_refused():
    mon = et.DFTMonitor(name="m", wavelengths=[1.55], components=("Hx",))
    with pytest.raises(NotImplementedError, match="'m' asks for Hx"):
        small_sim(monitors=[mon]).run()


def test_cuda_without_cupy_fails_loudly_and_auto_falls_back(monkeypatch):
    monkeypatch.setitem(sys.modules, "cupy", None)  # makes `import cupy` raise ImportError
    monkeypatch.delitem(sys.modules, "etalon.fdtd.backends.cupy_backend", raising=False)
    with pytest.raises(RuntimeError, match="needs CuPy"):
        get_backend("cuda", "single")
    assert isinstance(get_backend("auto", "single"), NumpyBackend)


def test_result_layout_per_monitor_type():
    wls = [1.5, 1.55, 1.6]
    monitors = [
        et.DFTMonitor(name="point", center=(0.31, 0.12, 0.0), wavelengths=wls),
        et.DFTMonitor(name="line", center=(0.0, 0.1, 0.0), size=(0.6, 0.0, 0.0), wavelengths=wls),
        et.DFTMonitor(name="plane", size=(2.0, 1.5, 0.0), wavelengths=wls, components=("Hz",)),
    ]
    result = small_sim(monitors=monitors).run()
    assert result.monitors == ["point", "line", "plane"]

    point = result["point"]["Ey"]
    assert point.dims == ("wavelength",)
    assert float(point.x) == 0.31 and float(point.y) == 0.12 and float(point.z) == 0.0
    assert list(point.wavelength.values) == wls
    np.testing.assert_allclose(point.frequency, et.C_0 / np.array(wls))
    assert point.dtype == np.complex64

    line = result["line"]["Hz"]
    assert line.dims == ("x", "wavelength") and float(line.y) == 0.1
    assert np.all(np.abs(line.x.values) <= 0.3 + 1e-9)

    plane = result["plane"]
    assert set(plane) == {"Hz"}
    x, y = result.grid.coords("Hz")
    region = result.grid.pml_layers
    np.testing.assert_allclose(plane["Hz"].x, x[region:-region])
    np.testing.assert_allclose(plane["Hz"].y, y[region:-region])
    assert plane["Hz"].dims == ("x", "y", "wavelength")

    with pytest.raises(KeyError, match="no monitor named 'nope'"):
        result["nope"]
    assert result.metadata["backend"] == "numpy"
    assert result.metadata["n_steps"] == result.grid.n_steps(20e-15)


def test_point_monitor_interpolation_matches_plane_nodes():
    """A point monitor equals bilinear interpolation of the same run's plane monitor."""
    wls = [1.55]
    monitors = [
        et.DFTMonitor(name="point", center=(0.31, 0.12, 0.0), wavelengths=wls, components=("Hz",)),
        et.DFTMonitor(name="plane", size=(2.0, 1.5, 0.0), wavelengths=wls, components=("Hz",)),
    ]
    result = small_sim(monitors=monitors, precision="double").run()
    plane = result["plane"]["Hz"].isel(wavelength=0)
    expected = plane.interp(x=0.31, y=0.12, method="linear")
    assert complex(result["point"]["Hz"].values[0]) == pytest.approx(complex(expected), rel=1e-12)
