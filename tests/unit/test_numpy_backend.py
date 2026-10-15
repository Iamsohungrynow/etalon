"""NumPy reference update: discrete energy invariant and exact mirror symmetry (plan-m0 U9, U10)."""

import numpy as np

import etalon as et
from etalon.constants import EPSILON_0, MU_0
from etalon.fdtd.backends.numpy_backend import NumpyBackend
from etalon.fdtd.cpml import CPMLAxis
from etalon.fdtd.solver import FDTDSolver
from etalon.fdtd.state import build_te_state
from etalon.grid.yee import YeeGrid2D, courant_time_step
from tests.sims import pulse


def _no_pml(n: int) -> CPMLAxis:
    return CPMLAxis(
        np.ones(n + 1), np.zeros(n + 1), np.ones(n + 1), np.ones(n), np.zeros(n), np.ones(n)
    )


def test_discrete_energy_is_conserved_in_a_pec_cavity():
    """W = ½Σε(Eⁿ)² + ½Σμ H^(n−½)H^(n+½) is exactly invariant under the leapfrog.

    Anisotropic cells (Δx ≠ Δy) and a dielectric block, so a swapped axis or a wrong
    sign in any difference breaks the invariant.
    """
    nx, ny, dx, dy = 40, 30, 0.05, 0.04
    grid = YeeGrid2D(
        nx=nx,
        ny=ny,
        dx=dx,
        dy=dy,
        dt=courant_time_step(0.99, dx, dy),
        pml_layers=0,
        x_min=0.0,
        y_min=0.0,
        z=0.0,
        courant=0.99,
    )
    eps = {c: np.ones(grid.shape(c)) for c in ("Ex", "Ey")}
    eps["Ex"][10:25, 8:20] = 4.0
    eps["Ey"][10:25, 8:20] = 4.0
    s = build_te_state(grid, eps, _no_pml(nx), _no_pml(ny), np.float64, lambda a: a)
    x, y = grid.coords("Hz")
    s.hz[...] = np.exp(-((x[:, None] - 0.8) ** 2 + (y[None, :] - 0.5) ** 2) / 0.02)

    backend = NumpyBackend()
    energies = []
    for _ in range(2000):
        hz_before = s.hz.copy()
        backend.update_h_te(s)
        w = 0.5 * EPSILON_0 * ((eps["Ex"] * s.ex**2).sum() + (eps["Ey"] * s.ey**2).sum())
        w += 0.5 * MU_0 * (hz_before * s.hz).sum()
        energies.append(w)
        backend.update_e_te(s)
    energies = np.array(energies)
    assert np.abs(s.ex).max() > 0  # the field really moved
    np.testing.assert_allclose(energies, energies[0], rtol=1e-11)


def test_centred_source_gives_bitwise_symmetric_fields():
    """Mirror x, mirror y and swap x↔y must hold exactly with a centred Hz source."""
    sim = et.Simulation(
        size=(41 * 0.05, 41 * 0.05, 0.0),  # odd cell count: the centre is an Hz node
        grid=et.UniformGrid(dl=0.05),
        boundary=et.PML(layers=8),
        sources=[et.PointSource(center=(0, 0, 0), component="Hz", pulse=pulse())],
        run_time=1e-15,
        precision="double",
        backend="numpy",
    )
    solver = FDTDSolver(sim)
    assert solver.injections[0].weights.size == 1
    for _ in range(300):
        solver.step()
    f = solver.fields()
    hz, ex, ey = f["Hz"], f["Ex"], f["Ey"]
    assert np.abs(hz).max() > 0
    np.testing.assert_array_equal(hz, hz[::-1, :])
    np.testing.assert_array_equal(hz, hz[:, ::-1])
    np.testing.assert_array_equal(hz, hz.T)
    np.testing.assert_array_equal(ex, ex[::-1, :])
    np.testing.assert_array_equal(ex, -ex[:, ::-1])
    np.testing.assert_array_equal(ey, -ey[::-1, :])
    np.testing.assert_array_equal(ey, -ex.T)
