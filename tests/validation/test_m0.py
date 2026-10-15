"""M0 physics validation against analytic results (plan-m0 V1–V6). CPU, ~40 s."""

import numpy as np
import pytest

from etalon.validation import m0

pytestmark = pytest.mark.validation


@pytest.fixture(scope="module")
def vacuum_cases():
    """0° and 45° at Δ = 0.1 µm (9–18 cells/λ) and Δ = 0.05 µm (18–36 cells/λ)."""
    return m0.dispersion_cases(0.1) + m0.dispersion_cases(0.05)


def test_v1_dispersion_matches_yee_relation(vacuum_cases):
    """Acceptance: |v_measured / v_Yee − 1| < 5e-3; enforced at 1e-3 (measured ≈ 1e-4)."""
    for case in vacuum_cases:
        residual = case.v_measured / case.v_theory - 1
        assert np.abs(residual).max() < 1e-3, (case.dl, case.angle, residual)


def test_v1_dispersion_anisotropy_is_resolved(vacuum_cases):
    """At 9 cells/λ the Yee grid is ~1.3 % slow on axis and ~0 on the diagonal; we must see it."""
    axis, diagonal = (c for c in vacuum_cases if c.dl == 0.1)
    coarsest = np.argmin(axis.cells_per_wavelength)
    assert axis.v_measured[coarsest] < 0.99
    assert diagonal.v_measured[coarsest] - axis.v_measured[coarsest] > 0.01


def test_v1_run_time_is_converged():
    """The 2D wake is not truncated: doubling run_time changes nothing that matters."""
    short = m0.dispersion_cases(0.05, run_time=200e-15)
    long = m0.dispersion_cases(0.05, run_time=400e-15)
    for a, b in zip(short, long, strict=True):
        assert np.abs(a.v_measured - b.v_measured).max() < 1e-4


def test_v2_raw_phase_velocity_within_half_percent(vacuum_cases):
    for case in vacuum_cases:
        resolved = case.cells_per_wavelength >= 20
        assert np.all(np.abs(case.v_measured[resolved] - 1) < 5e-3), (case.dl, case.angle)


def test_v3_uniform_dielectric():
    for case in m0.dispersion_cases(0.05, n=1.5):
        residual = case.v_measured / case.v_theory - 1
        assert np.abs(residual).max() < 1e-3, (case.angle, residual)


def test_v4_cpml_reflection():
    """Plan threshold −60 dB (1e-3); guarded at −80 dB (1e-4) — M0 measures −91 dB."""
    case = m0.cpml_reflection_case()
    assert np.abs(case.hz_reference).max() > 0
    for probe, error in zip(case.probes, case.error, strict=True):
        assert error < 1e-4, (probe, error)


def test_v5_late_time_stability():
    case = m0.late_time_case()
    energy = case.energy / case.energy.max()
    peak = int(np.argmax(energy))
    assert energy[-1] < 1e-8
    assert np.all(np.diff(energy[peak:]) <= 1e-12)  # never grows once the source is off


def test_v6_field_matches_2d_greens_function():
    """Absolute Hz vs −(ωε0/4) K̂ H0⁽¹⁾(k̃r): source normalisation, DFT Δt and signs together."""
    case = m0.green_function_case(dl=0.05)  # 26–36 cells per wavelength
    ratio = case.hz_measured / case.hz_analytic
    assert np.all(np.abs(ratio - 1) < 1e-2), ratio
