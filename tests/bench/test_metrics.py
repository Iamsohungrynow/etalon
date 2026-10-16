"""B4: derived quantities and gates, on synthetic spectra with known answers."""

import numpy as np
import pytest

from bench.metrics import (
    Metric,
    compare,
    coupling_ratio,
    find_resonances,
    fsr,
    imbalance_db,
    max_abs_s,
    power,
)
from tests.bench.fakes import ring_spectra

WL_RING = np.linspace(1.54, 1.56, 401)
WL = np.linspace(1.50, 1.60, 51)


def test_ring_resonances_recovered():
    s = ring_spectra(WL_RING, first=1.5435, fsr=0.008, fwhm=0.0017, depth=0.9)
    res = find_resonances(WL_RING, power(s["S31"]), power(s["S21"]))
    assert [r.wavelength for r in res] == pytest.approx([1.5435, 1.5515], abs=1e-8)
    assert [r.q for r in res] == pytest.approx([1.5435 / 0.0017, 1.5515 / 0.0017], rel=1e-4)
    assert fsr(res) == pytest.approx([0.008], abs=1e-7)
    f_coef = 1 / np.sin(np.pi * 0.0017 / (2 * 0.008)) ** 2
    t_max = 1 - 0.9 / (1 + f_coef)  # the through port between resonances (Airy)
    for r in res:
        assert r.drop_peak == pytest.approx(0.9, abs=1e-6)
        assert r.t_min == pytest.approx(0.1, abs=2e-3)
        assert r.extinction_db == pytest.approx(10 * np.log10(t_max / 0.1), abs=0.1)


def test_ring_resonances_with_noise():
    rng = np.random.default_rng(1)
    s = ring_spectra(WL_RING)
    drop = power(s["S31"]) + rng.normal(0, 1e-4, WL_RING.size)
    res = find_resonances(WL_RING, drop, power(s["S21"]))
    assert [r.wavelength for r in res] == pytest.approx([1.5435, 1.5515], abs=1e-6)
    assert [r.fwhm for r in res] == pytest.approx([0.0017, 0.0017], rel=2e-3)


def test_resonance_at_the_band_edge_is_skipped():
    s = ring_spectra(WL_RING, first=1.5405, fsr=0.0095)  # 1.5405 and 1.5595 sit at the edges
    res = find_resonances(WL_RING, power(s["S31"]), power(s["S21"]))
    assert [round(r.wavelength, 4) for r in res] == [1.55]


def test_simple_quantities():
    a, b = np.array([0.8 + 0j]), np.array([0.4j])
    assert imbalance_db(a, b) == pytest.approx(10 * np.log10(4))
    assert coupling_ratio(a, b) == pytest.approx(0.16 / 0.8)
    assert max_abs_s({"S21": a}, {"S21": a * 1j, "S31": b}) == pytest.approx(0.0)
    assert np.isnan(max_abs_s({"S21": a}, {"S31": b}))


def test_metric_pass_rules():
    assert Metric("x", 0.005, 0.01).passed is True
    assert Metric("x", 0.01, 0.01).passed is False
    assert Metric("x", None, 0.01).passed is False
    assert Metric("x", float("nan"), 0.01).passed is False
    assert Metric("x", 5.0).passed is None


def test_straight_gates_magnitude_and_neff():
    beta_l = 2 * np.pi * 2.5 * 10 / WL
    meep = {"S21": np.exp(1j * beta_l)}

    def gates(n_shift, magnitude=1.0):
        etalon = {"S21": magnitude * np.exp(1j * beta_l * (2.5 + n_shift) / 2.5)}
        result = compare("straight", WL, meep, etalon, length=10.0)
        return {m.name: m for m in result.metrics}

    # n_eff higher by 2e-3 (0.08 rad over 10 µm): passes, although complex |ΔS21| ≈ 0.08
    by_name = gates(2e-3)
    assert by_name["max |Δn_eff| implied by the S21 phase"].value == pytest.approx(2e-3, rel=1e-6)
    assert by_name["max |Δn_eff| implied by the S21 phase"].passed
    assert by_name["max | |S21|e − |S21|m |"].passed
    assert by_name["max |ΔS21| (complex)"].gate is None
    # n_eff higher by 4e-3: fails the n_eff gate (3e-3, Meep's own resolution-50 error)
    assert gates(4e-3)["max |Δn_eff| implied by the S21 phase"].passed is False
    # |S21| lower by 0.02: fails the magnitude gate
    assert gates(0.0, magnitude=0.98)["max | |S21|e − |S21|m |"].passed is False


def test_dc_and_mmi_power_gates():
    meep = {
        "S31": np.full(WL.shape, np.sqrt(0.5) + 0j),
        "S41": np.full(WL.shape, np.sqrt(0.5) * 1j),
    }
    etalon = {
        "S31": np.full(WL.shape, np.sqrt(0.505) + 0j),
        "S41": np.full(WL.shape, np.sqrt(0.485) * 1j),
    }
    metrics = compare("dc", WL, meep, etalon).metrics
    assert [m.value for m in metrics[:2]] == pytest.approx([0.005, 0.015])
    assert [m.passed for m in metrics[:2]] == [True, False]
    meep = {
        "S21": np.full(WL.shape, np.sqrt(0.48) + 0j),
        "S31": np.full(WL.shape, np.sqrt(0.48) + 0j),
    }
    etalon = {
        "S21": np.full(WL.shape, np.sqrt(0.49) + 0j),
        "S31": np.full(WL.shape, np.sqrt(0.47) + 0j),
    }
    metrics = compare("mmi", WL, meep, etalon).metrics
    assert metrics[2].value == pytest.approx(10 * np.log10(0.49 / 0.47))
    assert metrics[2].gate is None


def test_ring_gates():
    meep = ring_spectra(WL_RING)
    same = compare("ring", WL_RING, meep, ring_spectra(WL_RING))
    assert all(m.passed is not False for m in same.metrics)
    shifted = ring_spectra(WL_RING, first=1.5436)  # 0.1 nm = 1.25 % of the FSR
    result = compare("ring", WL_RING, meep, shifted)
    by_name = {m.name: m for m in result.metrics}
    assert by_name["max |Δλ_res| / FSR"].value == pytest.approx(0.0125, rel=1e-4)
    assert by_name["max |Δλ_res| / FSR"].passed is False
    assert by_name["max |ΔFSR| / FSR"].passed is True
    wider = ring_spectra(WL_RING, fwhm=0.0017 * 1.02)  # Q 2 % lower
    assert {m.name: m for m in compare("ring", WL_RING, meep, wider).metrics}[
        "max |ΔQ| / Q"
    ].passed is False


def test_ring_with_missing_resonance_fails():
    meep = ring_spectra(WL_RING)
    etalon = ring_spectra(WL_RING, fsr=0.016)  # one resonance in the band
    metrics = compare("ring", WL_RING, meep, etalon).metrics
    assert metrics[0].passed is False and metrics[0].value is None


def test_point2d_gate():
    t = np.exp(1j * WL)
    assert compare("point2d", WL, {"T21": t}, {"T21": t + 5e-4}).metrics[0].passed
    assert not compare("point2d", WL, {"T21": t}, {"T21": t + 2e-3}).metrics[0].passed
