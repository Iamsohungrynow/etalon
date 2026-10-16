"""B8: the etalon side — point2d runs; the five devices name the milestone they need."""

import numpy as np
import pytest

import etalon as et
from bench.config import load_config
from bench.devices import layout
from bench.etalon import run_device as adapter
from bench.schema import decode_complex

SMALL = ["devices.point2d.run_time_fs=20", "devices.point2d.band.points=3"]


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_point2d_simulation_matches_the_config(cfg):
    tier = cfg.tier("2d")
    sim = adapter.build(cfg, tier, layout(cfg, "point2d"), "numpy")
    assert sim.size == (8.0, 4.0, 0.0) and sim.center == (0.0, 0.0, 0.0)
    assert sim.grid.dl == pytest.approx(0.02)
    assert sim.boundary.layers == 50
    assert sim.courant == pytest.approx(0.70710678)
    assert sim.run_time == pytest.approx(300e-15)
    assert sim.medium.n == cfg.materials.sio2
    (source,) = sim.sources
    assert source.component == "Hz" and source.center == (-2.99, 0.01, 0.0)
    assert source.pulse.wavelength == pytest.approx(1.55)
    assert source.pulse.bandwidth == pytest.approx(0.1)
    assert [m.center for m in sim.monitors] == [(-1.99, 0.01, 0.0), (2.01, 0.01, 0.0)]
    assert np.allclose(sim.monitors[0].wavelengths, np.linspace(1.5, 1.6, 51))


def test_point2d_runs_on_numpy():
    cfg = load_config(overrides=SMALL)
    run = adapter.run_backend(cfg, "2d", layout(cfg, "point2d"), "numpy")
    assert run.status == "ok" and run.grid.cells == (500, 300)
    t = decode_complex(run.s["T21"])
    assert t.shape == (3,) and np.all(np.isfinite(t))


@pytest.mark.parametrize("device", ["straight", "bend", "dc", "mmi", "ring"])
def test_five_devices_need_m1(cfg, device):
    run = adapter.run_backend(cfg, "2d", layout(cfg, device), "numpy")
    assert run.status == "unsupported" and run.needs == "M1"
    for feature in ("ModeSource", "ModePortMonitor", "PolySlab"):
        assert feature in run.message
    assert "3D" not in run.message


def test_3d_tier_also_needs_3d(cfg):
    run = adapter.run_backend(cfg, "3d", layout(cfg, "dc"), "cuda")
    assert run.status == "unsupported"
    assert run.message.endswith(f"(not in etalon {et.__version__} yet)")
    assert "3D" in run.message


def test_cuda_skipped_without_a_device(monkeypatch):
    cfg = load_config(overrides=SMALL)
    monkeypatch.setattr(adapter, "cuda_available", lambda: False)
    run = adapter.run_backend(cfg, "2d", layout(cfg, "point2d"), "cuda")
    assert run.status == "skipped" and "CUDA" in run.message


def test_long_cpu_runs_are_timed_partially_and_extrapolated(monkeypatch):
    cfg = load_config(overrides=[*SMALL, "etalon.cpu_full_run_max_minutes=1e-9"])
    monkeypatch.setattr(adapter, "PARTIAL_STEPS", 5)
    run = adapter.run_backend(cfg, "2d", layout(cfg, "point2d"), "numpy")
    assert run.status == "ok" and run.extrapolated and not run.s
    assert run.stepping_time_s > 0 and run.wall_time_s >= run.stepping_time_s
