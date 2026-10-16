"""B1: bench/config.yaml loads, rejects mistakes, and derives the numbers both codes use."""

import copy
import math

import numpy as np
import pytest
import yaml
from pydantic import ValidationError
from scipy.optimize import brentq

import etalon as et
from bench.config import CONFIG_PATH, BenchConfig, load_config, meep_frequency, meep_time, pulse


@pytest.fixture(scope="module")
def raw() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cfg() -> BenchConfig:
    return load_config()


def validate(data: dict) -> BenchConfig:
    return BenchConfig.model_validate(data)


def test_config_loads(cfg):
    assert set(cfg.tiers) == {"2d", "3d"}
    assert cfg.tier("2d").devices[0] == "point2d"
    assert cfg.devices.dc.gap == 0.236


def test_unknown_key_is_an_error_naming_it(raw):
    data = copy.deepcopy(raw)
    data["devices"]["straight"]["lenght"] = 10.0
    with pytest.raises(ValidationError, match="lenght"):
        validate(data)


def test_region_must_be_an_even_number_of_cells(raw):
    data = copy.deepcopy(raw)
    data["devices"]["straight"]["region"]["size"] = [12.02, 4.0]  # 601 cells
    with pytest.raises(ValidationError, match="even number of cells"):
        validate(data)


def test_region_centre_must_be_on_a_node(raw):
    data = copy.deepcopy(raw)
    data["devices"]["bend"]["region"]["center"] = [2.21, 2.8]
    with pytest.raises(ValidationError, match="whole number of cells"):
        validate(data)


def test_pml_must_be_whole_cells(raw):
    data = copy.deepcopy(raw)
    data["tiers"]["3d"]["pml"] = 0.51
    with pytest.raises(ValidationError, match="pml"):
        validate(data)


def test_point2d_points_must_sit_on_hz_nodes(raw):
    data = copy.deepcopy(raw)
    data["devices"]["point2d"]["probes"][1] = [2.0, 0.01]
    with pytest.raises(ValidationError, match="probes"):
        validate(data)


def test_tier_rules(raw):
    data = copy.deepcopy(raw)
    data["tiers"]["3d"]["devices"] = ["point2d"]
    with pytest.raises(ValidationError, match="2D device"):
        validate(data)
    data = copy.deepcopy(raw)
    data["tiers"]["2d"]["courant_meep"] = 0.75
    with pytest.raises(ValidationError, match="stability"):
        validate(data)
    data = copy.deepcopy(raw)
    data["tiers"]["2d"]["devices"] = ["straight", "nosuchdevice"]
    with pytest.raises(ValidationError):
        validate(data)


def test_unknown_tier_or_device_names_the_options(cfg):
    with pytest.raises(ValueError, match="2d"):
        cfg.tier("4d")
    with pytest.raises(ValueError, match="straight"):
        cfg.device("coupler")
    with pytest.raises(ValueError, match="not in tier"):
        cfg.device_spec("3d", "ring")


def test_courant_mapping(cfg):
    """etalon courant = S·√D gives Meep's Δt = S·Δx/c (plan-m0 §8)."""
    for tier in cfg.tiers.values():
        dl = tier.dl * 1e-6
        dt_meep = tier.courant_meep * dl / 299_792_458.0
        dt_etalon = tier.courant_etalon / (299_792_458.0 * math.sqrt(tier.dims / dl**2))
        assert dt_etalon == pytest.approx(dt_meep, rel=1e-14)
    assert cfg.tier("2d").courant_etalon == pytest.approx(0.70710678)
    assert cfg.tier("3d").courant_etalon == pytest.approx(0.8660254)
    assert cfg.tier("2d").pml_layers == 50
    assert cfg.tier("3d").pml_layers == 25


def test_meep_units():
    assert meep_frequency(1.55) == pytest.approx(0.6451613)
    assert meep_time(1.0) == pytest.approx(0.299792458)
    assert meep_time(3.33564095198152) == pytest.approx(1.0)


def test_meep_pulse_matches_etalon_pulse(cfg):
    """Meep's w = 1/fwidth (in a/c) equals etalon's τ, so both pulses share envelope and delay."""
    for name in ("straight", "ring"):
        band = cfg.device(name).band
        p = pulse(band)
        gp = et.GaussianPulse(wavelength=p.wavelength, bandwidth=p.bandwidth)
        assert p.tau == pytest.approx(gp.width, rel=1e-12)
        assert p.sigma_f == pytest.approx(gp.frequency_width, rel=1e-12)
        w_meep_s = (1.0 / p.meep_fwidth) * 1e-6 / 299_792_458.0
        assert w_meep_s == pytest.approx(gp.width, rel=1e-12)
        assert p.meep_cutoff * w_meep_s == pytest.approx(gp.delay, rel=1e-12)
        assert p.meep_frequency * 299_792_458.0 / 1e-6 == pytest.approx(gp.frequency, rel=1e-12)


def test_core_index_is_the_slab_te0_index(cfg):
    """2D tier core index: TE0 root of the symmetric slab, tan(κt/2) = γ/κ, at 1.55 µm."""
    n_si, n_ox, t = cfg.materials.si, cfg.materials.sio2, cfg.strip.thickness
    k0 = 2 * np.pi / 1.55

    def te0(n):
        kappa = k0 * np.sqrt(n_si**2 - n**2)
        gamma = k0 * np.sqrt(n**2 - n_ox**2)
        return np.tan(kappa * t / 2) - gamma / kappa

    n_eff = brentq(te0, n_ox + 1e-9, n_si - 1e-9, xtol=1e-12)
    assert cfg.tier("2d").core_index == pytest.approx(n_eff, abs=5e-6)


def test_band_wavelengths(cfg):
    wl = cfg.devices.ring.band.wavelengths()
    assert wl[0] == 1.535 and wl[-1] == 1.565 and wl.size == 601
    assert np.allclose(np.diff(wl), 5e-5)


def test_hash_is_stable_and_sensitive(raw, cfg):
    reordered = validate(dict(reversed(list(copy.deepcopy(raw).items()))))
    assert reordered.config_sha256("2d", "dc") == cfg.config_sha256("2d", "dc")
    changed = copy.deepcopy(raw)
    changed["devices"]["dc"]["gap"] = 0.2
    other = validate(changed)
    assert other.config_sha256("2d", "dc") != cfg.config_sha256("2d", "dc")
    # a change to one device leaves the others' hashes (and cached Meep results) alone
    assert other.config_sha256("2d", "mmi") == cfg.config_sha256("2d", "mmi")
    # solver-only settings do not invalidate results
    solver_only = copy.deepcopy(raw)
    solver_only["meep"]["processes"] = 12
    solver_only["etalon"]["precision"] = "double"
    assert validate(solver_only).config_sha256("2d", "dc") == cfg.config_sha256("2d", "dc")
    # the same device in another tier is a different comparison
    assert cfg.config_sha256("3d", "straight") != cfg.config_sha256("2d", "straight")
