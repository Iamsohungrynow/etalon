"""Pulse, CPML profiles, injection weights and DFT sampling (plan-m0 U5–U8)."""

import math

import numpy as np
import pytest

import etalon as et
from etalon.constants import EPSILON_0, ETA_0, MU_0, UM
from etalon.fdtd import solver as solver_module
from etalon.fdtd.cpml import cpml_axis, pml_depth
from etalon.fdtd.dft import axis_sampling, dft_phasors, monitor_samplings
from etalon.fdtd.solver import FDTDSolver
from etalon.fdtd.sources import point_injection, pulse_signal
from etalon.grid.materials import permittivity_on_nodes
from etalon.grid.yee import build_yee_grid
from tests.sims import pulse, small_sim

# ---------------------------------------------------------------- U5 pulse


def test_pulse_is_zero_mean_and_starts_quietly():
    p = pulse(wavelength=1.35, bandwidth=0.9)  # very broad band
    dt = p.width / 50
    full = p.delay + np.arange(-400, 401) * dt  # symmetric about the peak: exactly zero mean
    g = pulse_signal(p, full)
    assert abs(g.sum()) < 1e-13 * np.abs(g).sum()
    # A run starts at t = 0, 5τ before the peak; what that truncation leaves is ~e^(−12.5)
    g_run = pulse_signal(p, np.arange(0, 2 * p.delay, dt))
    assert abs(g_run.sum()) < 1e-6 * np.abs(g_run).sum()
    assert abs(pulse_signal(p, 0.0)) <= math.exp(-12.5)


def test_pulse_spectrum_matches_analytic():
    p = pulse(amplitude=2.0)
    dt = p.width / 40
    t = p.delay + np.arange(-500, 501) * dt  # ±12.5τ: the whole Gaussian
    omega = 2 * np.pi * et.wvl_to_freq(np.linspace(1.3, 1.8, 11))
    numeric = (pulse_signal(p, t)[None, :] * np.exp(1j * omega[:, None] * t[None, :])).sum(1) * dt
    w0, tau = 2 * np.pi * p.frequency, p.width
    analytic = (
        p.amplitude
        * np.exp(1j * omega * p.delay)
        * tau
        * np.sqrt(2 * np.pi)
        / 2j
        * (np.exp(-((omega + w0) ** 2) * tau**2 / 2) - np.exp(-((omega - w0) ** 2) * tau**2 / 2))
    )
    np.testing.assert_allclose(numeric, analytic, rtol=1e-9)


# ---------------------------------------------------------------- U6 CPML


def test_pml_depth_profiles():
    rho_e, rho_h = pml_depth(n_cells=12, layers=4)
    np.testing.assert_allclose(rho_e[:5], [1, 0.75, 0.5, 0.25, 0])
    np.testing.assert_allclose(rho_h[:4], [0.875, 0.625, 0.375, 0.125])
    assert np.all(rho_e[5:8] == 0) and np.all(rho_h[4:8] == 0)
    np.testing.assert_array_equal(rho_e, rho_e[::-1])
    np.testing.assert_array_equal(rho_h, rho_h[::-1])


def test_cpml_coefficients():
    pml = et.PML(layers=6, kappa_max=3.0)
    dt, spacing = 1e-16, 0.05
    ax = cpml_axis(n_cells=30, spacing=spacing, dt=dt, pml=pml, eps_r=1.0)
    for b, c, ik in ((ax.b_e, ax.c_e, ax.inv_kappa_e), (ax.b_h, ax.c_h, ax.inv_kappa_h)):
        interior = slice(7, -7)
        assert np.all(b[interior] == 1.0) and np.all(c[interior] == 0.0)
        assert np.all(ik[interior] == 1.0)
        assert np.all((b > 0) & (b <= 1)) and np.all(c <= 0)
        np.testing.assert_array_equal(b, b[::-1])
    # outer face (ρ = 1), α = 0: σ = σ_max, κ = κ_max, b = exp(−σΔt/(κε0)), c = (b − 1)/κ
    sigma_max = 0.8 * 4 / (ETA_0 * spacing * UM)
    b0 = math.exp(-sigma_max / 3.0 * dt / EPSILON_0)
    assert ax.b_e[0] == pytest.approx(b0, rel=1e-14)
    assert ax.c_e[0] == pytest.approx((b0 - 1) / 3.0, rel=1e-14)
    assert ax.inv_kappa_e[0] == pytest.approx(1 / 3.0)
    assert ax.b_e[6] == 1.0  # node L sits on the region boundary: ρ = 0


# ---------------------------------------------------------------- U7 injection


def test_bilinear_weights_reproduce_position():
    src = et.PointSource(center=(0.013, -0.031, 0.0), component="Ey", pulse=pulse())
    sim = small_sim(sources=[src], medium=et.Medium(n=1.5))
    grid = build_yee_grid(sim)
    inj = point_injection(src, grid, permittivity_on_nodes(sim, grid))
    x, y = grid.coords("Ey")
    assert inj.weights.size == 4
    assert inj.weights.sum() == pytest.approx(1.0, abs=1e-15)
    assert (inj.weights * x[inj.i]).sum() == pytest.approx(0.013, abs=1e-12)
    assert (inj.weights * y[inj.j]).sum() == pytest.approx(-0.031, abs=1e-12)
    area = grid.dx * grid.dy * UM**2
    expected = grid.dt / (EPSILON_0 * 2.25) * inj.weights / area
    np.testing.assert_allclose(inj.coefficient, expected, rtol=1e-15)
    assert inj.sample_time(3, grid.dt) == pytest.approx(3.5 * grid.dt)  # J at (n + ½)Δt


def test_on_node_magnetic_source_uses_one_node():
    sim = small_sim()
    grid = build_yee_grid(sim)
    x, y = grid.coords("Hz")
    src = et.PointSource(center=(x[20], y[17], 0.0), component="Hz", pulse=pulse())
    inj = point_injection(src, grid, permittivity_on_nodes(sim, grid))
    assert list(inj.i) == [20] and list(inj.j) == [17]
    assert inj.coefficient[0] == pytest.approx(grid.dt / MU_0 / (grid.dx * grid.dy * UM**2))
    assert inj.sample_time(3, grid.dt) == pytest.approx(3 * grid.dt)  # M at nΔt


# ---------------------------------------------------------------- U8 DFT sampling


def test_axis_sampling_rules():
    nodes = np.arange(11) * 0.1
    s = axis_sampling(nodes, center=0.5, size=0.2, what="m")
    np.testing.assert_array_equal(s.index, [4, 5, 6])  # faces included
    assert s.weights is None
    s = axis_sampling(nodes, center=0.53, size=0.0, what="m")
    np.testing.assert_array_equal(s.index, [5, 6])
    np.testing.assert_allclose(s.weights, [0.7, 0.3])
    s = axis_sampling(nodes, center=0.5, size=0.0, what="m")
    np.testing.assert_array_equal(s.index, [5])
    with pytest.raises(ValueError, match="thinner than one cell"):
        axis_sampling(nodes, center=0.55, size=0.02, what="m")


def test_monitor_flat_index_matches_nodes():
    mon = et.DFTMonitor(
        name="box", center=(0.1, 0.0, 0.0), size=(0.4, 0.3, 0.0), wavelengths=[1.55]
    )
    grid = build_yee_grid(small_sim(monitors=[mon]))
    for sampling in monitor_samplings(mon, grid):
        x, y = grid.coords(sampling.component)
        flat_x = np.repeat(sampling.x.index, sampling.y.index.size)
        flat_y = np.tile(sampling.y.index, sampling.x.index.size)
        np.testing.assert_array_equal(
            sampling.flat_index,
            np.ravel_multi_index((flat_x, flat_y), grid.shape(sampling.component)),
        )
        assert np.all(np.abs(x[sampling.x.index] - 0.1) <= 0.2 + 1e-9)
        assert np.all(np.abs(y[sampling.y.index]) <= 0.15 + 1e-9)


def test_dft_times_are_half_step_for_h_and_full_step_for_e():
    solver = FDTDSolver(small_sim())
    dt = solver.grid.dt
    for mon in solver.monitors:
        f = mon.sampling.frequencies
        for n in (0, 7):
            solver.n = n
            ph_h, ph_e = solver._phasor_rows(mon)
            np.testing.assert_allclose(
                ph_h, dft_phasors(f, np.array([(n + 0.5) * dt]), dt)[0], rtol=1e-6
            )
            np.testing.assert_allclose(
                ph_e, dft_phasors(f, np.array([(n + 1.0) * dt]), dt)[0], rtol=1e-6
            )


def test_phasor_tables_hold_no_more_steps_than_the_run_has_left(monkeypatch):
    """A run shorter than a chunk builds one table of n_steps rows on its first step."""
    solver = FDTDSolver(small_sim())
    solver.step()
    for mon in solver.monitors:
        assert mon.chunk > solver.n_steps
        assert mon.table[0].shape == mon.table[1].shape == (solver.n_steps, 2)
    tables = [mon.table for mon in solver.monitors]
    solver.run()
    assert all(mon.table is table for mon, table in zip(solver.monitors, tables, strict=True))

    # Two full chunks, then a last table of only the steps left; past the end, a full chunk.
    n_steps = solver.n_steps
    chunk = n_steps // 3 + 1
    monkeypatch.setattr(solver_module, "_PHASOR_TABLE_ENTRIES", 2 * chunk)
    solver = FDTDSolver(small_sim())
    solver.run()
    mon = solver.monitors[0]
    assert mon.chunk == chunk
    assert mon.table_start == 2 * chunk
    assert mon.table[0].shape[0] == n_steps - 2 * chunk < chunk
    solver.step()
    assert mon.table_start == n_steps
    assert mon.table[0].shape[0] == chunk


@pytest.mark.parametrize("precision", ["single", "double"])
def test_phasor_table_size_leaves_the_result_bitwise_unchanged(monkeypatch, precision):
    """Capped, short-chunk and uncapped tables give identical accumulators.

    A phasor depends only on its own step, so how many steps a table holds must
    not change a bit of the result. "Uncapped" is the behaviour before tables
    were capped at the run's end: one full chunk, whatever the run length.
    """
    monitors = [
        et.DFTMonitor(name="probe", center=(0.5, 0.0, 0.0), wavelengths=[1.5, 1.55, 1.6]),
        et.DFTMonitor(
            name="plane", size=(1.0, 0.6, 0.0), wavelengths=[1.31, 1.55], components=("Hz",)
        ),
    ]
    sim = small_sim(monitors=monitors, precision=precision)

    def accumulators(entries, capped):
        monkeypatch.setattr(solver_module, "_PHASOR_TABLE_ENTRIES", entries)
        solver = FDTDSolver(sim)
        n_steps = solver.n_steps
        if not capped:
            solver.n_steps = 10**9  # the tables no longer see the end of the run
        for _ in range(n_steps):
            solver.step()
        return [solver.backend.to_host(mon.acc) for mon in solver.monitors]

    capped = accumulators(1 << 22, capped=True)  # one table of n_steps rows
    uncapped = accumulators(6 * 1000, capped=False)  # one table of 2000 or 3000 rows
    short = accumulators(6 * 7, capped=True)  # refilled every 14 or 21 steps
    for a, b, c in zip(capped, uncapped, short, strict=True):
        assert np.abs(a).max() > 0
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(a, c)


def test_dft_of_a_tone_over_whole_periods():
    f0 = 200e12
    dt = 1 / f0 / 64
    times = (np.arange(64 * 5) + 0.5) * dt
    signal = np.cos(2 * np.pi * f0 * times)
    acc = (signal[:, None] * dft_phasors(np.array([f0]), times, dt)).sum(0)
    assert acc[0] == pytest.approx(5 / f0 / 2, rel=1e-12)  # ∫cos·e^{iωt} = T/2 over whole periods
