"""CUDA kernels vs the NumPy reference (plan-m0 G1–G5).

Contract: ‖gpu − cpu‖∞ ≤ rtol · ‖cpu‖∞ per array, rtol = 1e-5 (float32) or 1e-12
(float64). Element-wise rtol is meaningless where a field crosses zero. Each test
also prints whether the agreement is bitwise (run with -s to see it).
"""

import numpy as np
import pytest

cp = pytest.importorskip("cupy")

import etalon as et  # noqa: E402
from etalon.fdtd.backends import get_backend  # noqa: E402
from etalon.fdtd.backends.cupy_backend import CupyBackend  # noqa: E402
from etalon.fdtd.backends.numpy_backend import NumpyBackend  # noqa: E402
from etalon.fdtd.cpml import CPMLAxis  # noqa: E402
from etalon.fdtd.solver import FDTDSolver  # noqa: E402
from etalon.fdtd.state import build_te_state  # noqa: E402
from etalon.grid.yee import YeeGrid2D, courant_time_step  # noqa: E402

pytestmark = pytest.mark.gpu

PRECISIONS = [("single", np.float32, 1e-5), ("double", np.float64, 1e-12)]
FIELDS = ("ex", "ey", "hz", "psi_ex_y", "psi_ey_x", "psi_hz_x", "psi_hz_y")


def assert_close(gpu, cpu, rtol, label):
    gpu, cpu = np.asarray(gpu), np.asarray(cpu)
    scale = np.abs(cpu).max()
    error = np.abs(gpu - cpu).max()
    assert error <= rtol * scale, f"{label}: max |gpu − cpu| = {error:.3e}, ‖cpu‖∞ = {scale:.3e}"
    return error == 0


def random_states(dtype, seed=1):
    """The same random TE state on both backends: odd sizes, random ε and CPML profiles."""
    rng = np.random.default_rng(seed)
    nx, ny, dx, dy = 67, 53, 0.05, 0.04
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
    eps = {c: rng.uniform(1.0, 12.0, grid.shape(c)) for c in ("Ex", "Ey")}

    def axis(n):
        return CPMLAxis(
            rng.uniform(0.2, 1.0, n + 1),
            -rng.uniform(0, 0.8, n + 1),
            rng.uniform(0.3, 1.0, n + 1),
            rng.uniform(0.2, 1.0, n),
            -rng.uniform(0, 0.8, n),
            rng.uniform(0.3, 1.0, n),
        )

    cx, cy = axis(nx), axis(ny)
    initial = {
        name: rng.standard_normal(shape).astype(dtype)
        for name, shape in [("ex", grid.shape("Ex")), ("ey", grid.shape("Ey")),
                            ("hz", grid.shape("Hz")), ("psi_ex_y", grid.shape("Ex")),
                            ("psi_ey_x", grid.shape("Ey")), ("psi_hz_x", grid.shape("Hz")),
                            ("psi_hz_y", grid.shape("Hz"))]
    }  # fmt: skip
    initial["hz"] *= 1 / 377.0  # SI-like H/E ratio
    states = []
    for to_device in (lambda a: a, cp.asarray):
        s = build_te_state(grid, eps, cx, cy, dtype, to_device)
        for name, value in initial.items():
            setattr(s, name, to_device(value.copy()))
        states.append(s)
    return states


@pytest.mark.parametrize(("precision", "dtype", "rtol"), PRECISIONS)
@pytest.mark.parametrize("update", ["update_h_te", "update_e_te"])
def test_g1_g2_update_kernels(precision, dtype, rtol, update):
    cpu_state, gpu_state = random_states(dtype)
    getattr(NumpyBackend(), update)(cpu_state)
    getattr(CupyBackend(precision), update)(gpu_state)
    bitwise = all(
        assert_close(cp.asnumpy(getattr(gpu_state, f)), getattr(cpu_state, f), rtol, f)
        for f in FIELDS
    )
    print(f"\n{update} [{precision}]: bitwise identical = {bitwise}")


@pytest.mark.parametrize(("precision", "dtype", "rtol"), PRECISIONS)
def test_g3_dft_kernel(precision, dtype, rtol):
    rng = np.random.default_rng(2)
    complex_dtype = np.complex64 if dtype == np.float32 else np.complex128
    field = rng.standard_normal((67, 54)).astype(dtype)
    index = rng.choice(field.size, size=301, replace=False).astype(np.int64)
    phasors = np.exp(1j * rng.uniform(0, 2 * np.pi, 13)).astype(complex_dtype) * 1e-16
    acc = (rng.standard_normal((13, 301)) + 1j * rng.standard_normal((13, 301))) * 1e-15
    acc = acc.astype(complex_dtype)
    acc_gpu = cp.asarray(acc)
    NumpyBackend().accumulate_dft(acc, field, index, phasors)
    CupyBackend(precision).accumulate_dft(
        acc_gpu, cp.asarray(field), cp.asarray(index), cp.asarray(phasors)
    )
    bitwise = assert_close(cp.asnumpy(acc_gpu), acc, rtol, "acc")
    print(f"\naccumulate_dft [{precision}]: bitwise identical = {bitwise}")


def full_sim(backend, precision):
    si = et.Medium(n=3.476)
    return et.Simulation(
        size=(131 * 0.03, 97 * 0.03, 0.0),
        grid=et.UniformGrid(dl=0.03),
        medium=et.Medium(n=1.444),
        structures=[et.Box(center=(0.3, -0.2, 0.0), size=(1.5, 0.5, 0.22), medium=si)],
        boundary=et.PML(layers=10, kappa_max=2.0),
        sources=[
            et.PointSource(
                center=(-1.234, 0.071, 0.0),
                component="Ey",
                pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.3),
            ),
            et.PointSource(
                center=(0.517, 0.633, 0.0),
                component="Hz",
                pulse=et.GaussianPulse(wavelength=1.31, bandwidth=0.2, amplitude=0.5),
            ),
        ],
        monitors=[
            et.DFTMonitor(
                name="point", center=(1.11, -0.37, 0.0), wavelengths=np.linspace(1.3, 1.7, 9)
            ),
            et.DFTMonitor(name="plane", size=(3.0, 2.0, 0.0), wavelengths=[1.31, 1.55]),
        ],
        run_time=1.0,  # not used: the test steps a fixed number of times
        precision=precision,
        backend=backend,
    )


@pytest.mark.parametrize(("precision", "dtype", "rtol"), PRECISIONS)
def test_g4_full_run(precision, dtype, rtol):
    solvers = [FDTDSolver(full_sim(b, precision)) for b in ("numpy", "cuda")]
    assert solvers[1].backend.name == "cuda"
    for solver in solvers:
        for _ in range(600):
            solver.step()
    cpu, gpu = solvers
    bitwise = True
    for name, value in cpu.fields().items():
        assert np.abs(value).max() > 0
        bitwise &= assert_close(gpu.fields()[name], value, rtol, name)
    for mc, mg in zip(cpu.monitors, gpu.monitors, strict=True):
        label = f"{mc.sampling.monitor}/{mc.sampling.component}"
        bitwise &= assert_close(cp.asnumpy(mg.acc), mc.acc, rtol, label)
    print(f"\nfull run, 600 steps [{precision}]: bitwise identical = {bitwise}")


@pytest.mark.parametrize(("precision", "dtype", "rtol"), PRECISIONS)
def test_g4b_short_run_builds_tables_of_its_own_length(precision, dtype, rtol):
    """A run shorter than a phasor chunk, to its end: tables of n_steps rows, same monitors."""
    sims = [
        full_sim(b, precision).model_copy(update={"run_time": 40e-15}) for b in ("numpy", "cuda")
    ]
    solvers = [FDTDSolver(sim) for sim in sims]
    for solver in solvers:
        solver.run()
        for mon in solver.monitors:
            assert mon.table[0].shape[0] == solver.n_steps < mon.chunk
    cpu, gpu = solvers
    bitwise = True
    for mc, mg in zip(cpu.monitors, gpu.monitors, strict=True):
        label = f"{mc.sampling.monitor}/{mc.sampling.component}"
        assert np.abs(mc.acc).max() > 0
        bitwise &= assert_close(cp.asnumpy(mg.acc), mc.acc, rtol, label)
    print(f"\nshort run, {cpu.n_steps} steps [{precision}]: bitwise identical = {bitwise}")


def test_g5_auto_picks_cuda():
    assert get_backend("auto", "single").name == "cuda"
    result = full_sim("auto", "single").model_copy(update={"run_time": 5e-15}).run()
    assert result.metadata["backend"] == "cuda"
    assert result.metadata["device"].startswith("cuda:0")
