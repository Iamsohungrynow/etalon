"""M0 validation cases: 2D vacuum propagation, CPML, late-time stability, source normalisation.

Each function runs small simulations and returns plain NumPy data; the pass/fail
thresholds live in tests/validation and the plots in bench/validate_m0.py. The
same cases back Studio's Validation page, so they run on any user's machine.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.special import hankel1

import etalon as et
from etalon.analysis.dispersion import measured_phase_velocity, numerical_phase_velocity
from etalon.constants import EPSILON_0, MU_0, UM
from etalon.fdtd.solver import FDTDSolver
from etalon.fdtd.sources import pulse_signal

# A broad pulse covering 9-36 cells per wavelength on 0.1 / 0.05 µm grids.
BROADBAND = et.GaussianPulse(wavelength=1.35, bandwidth=0.9)
BROADBAND_WAVELENGTHS = np.linspace(0.9, 1.8, 19)


def _centred_size(half_width: float, dl: float) -> float:
    """Region size with an odd number of cells, so the origin is an Hz node."""
    return (2 * math.ceil(half_width / dl) + 1) * dl


@dataclass
class DispersionCase:
    """Phase velocity measured between two probes vs the Yee relation."""

    dl: float
    angle: float
    n: float
    wavelengths: NDArray[np.float64]
    cells_per_wavelength: NDArray[np.float64]
    """λ / (n Δ): cells per wavelength in the medium."""
    v_measured: NDArray[np.float64]
    """ṽp / (c/n), measured."""
    v_theory: NDArray[np.float64]
    """ṽp / (c/n), Yee dispersion relation."""


def dispersion_cases(
    dl: float,
    n: float = 1.0,
    run_time: float = 200e-15,
    r_near: float = 1.5,
    r_far: float = 4.5,
    backend: str = "numpy",
    pulse: et.GaussianPulse = BROADBAND,
    wavelengths: NDArray[np.float64] = BROADBAND_WAVELENGTHS,
) -> list[DispersionCase]:
    """One run, Hz point source at an Hz node, Hz probes on Hz nodes along 0° and 45°.

    Only the lattice symmetry directions are measured: there the ray direction equals
    the wave-vector direction, so the probe phase follows k̃(φ) exactly.
    """
    m_axis = (round(r_near / dl), round(r_far / dl))
    m_diag = (round(r_near / (math.sqrt(2) * dl)), round(r_far / (math.sqrt(2) * dl)))
    probes = {
        0.0: [(m * dl, 0.0, m * dl) for m in m_axis],
        45.0: [(m * dl, m * dl, math.sqrt(2) * m * dl) for m in m_diag],
    }
    monitors = [
        et.DFTMonitor(
            name=f"{angle:g}-{i}", center=(x, y, 0.0), wavelengths=wavelengths, components=("Hz",)
        )
        for angle, points in probes.items()
        for i, (x, y, _) in enumerate(points)
    ]
    size = _centred_size(r_far + 1.0, dl)
    sim = et.Simulation(
        size=(size, size, 0.0),
        medium=et.Medium(n=n),
        grid=et.UniformGrid(dl=dl),
        boundary=et.PML(layers=12),
        sources=[et.PointSource(center=(0.0, 0.0, 0.0), component="Hz", pulse=pulse)],
        monitors=monitors,
        run_time=run_time,
        backend=backend,
    )
    result = sim.run()
    cases = []
    for angle, points in probes.items():
        (_, _, r1), (_, _, r2) = points
        v_measured = measured_phase_velocity(
            near=result[f"{angle:g}-0"]["Hz"],
            far=result[f"{angle:g}-1"]["Hz"],
            r_near=r1,
            r_far=r2,
            wave="cylindrical",
            n=n,
        )
        v_theory = numerical_phase_velocity(wavelengths, result.grid, angle=angle, n=n)
        cases.append(
            DispersionCase(
                dl, angle, n, np.asarray(wavelengths), wavelengths / (n * dl), v_measured, v_theory
            )
        )
    return cases


@dataclass
class ReflectionCase:
    """Hz(t) at probes near the PML, small domain vs a domain too large to reflect in time."""

    t: NDArray[np.float64]
    probes: list[str]
    hz_small: NDArray[np.float64]
    """(n_t, n_probes)"""
    hz_reference: NDArray[np.float64]
    error: NDArray[np.float64]
    """max_t |Hz − Hz_ref| / max_t |Hz_ref| per probe."""


def cpml_reflection_case(
    layers: int = 12, run_time: float = 100e-15, backend: str = "numpy"
) -> ReflectionCase:
    """Classic CPML test (Taflove & Hagness, ch. 7): compare with a reflection-free reference."""
    dl = 0.05
    size = _centred_size(1.5, dl)  # 3.05 µm
    edge = size / 2.0
    probe_xy = {
        "side": (edge - 2.5 * dl, 0.0),  # Hz nodes 2 cells inside the region
        "corner": (edge - 2.5 * dl, edge - 2.5 * dl),
    }
    source = et.PointSource(
        center=(0.0, 0.0, 0.0),
        component="Hz",
        pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.5),
    )
    margin = et.C_0 * run_time / 2.0  # µm: reflections from farther out arrive too late

    def record(region: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        sim = et.Simulation(
            size=(region, region, 0.0),
            grid=et.UniformGrid(dl=dl),
            boundary=et.PML(layers=layers),
            sources=[source],
            run_time=run_time,
            backend=backend,
        )
        solver = FDTDSolver(sim)
        x, y = solver.grid.coords("Hz")
        idx = [
            (int(np.argmin(np.abs(x - px))), int(np.argmin(np.abs(y - py))))
            for px, py in probe_xy.values()
        ]
        trace = np.empty((solver.n_steps, len(idx)))
        for n in range(solver.n_steps):
            solver.step()
            for k, (i, j) in enumerate(idx):
                trace[n, k] = float(solver.state.hz[i, j])
        t = np.asarray((np.arange(solver.n_steps) + 0.5) * solver.grid.dt, dtype=np.float64)
        return t, trace

    t, small = record(size)
    _, reference = record(_centred_size(1.5 + margin, dl))
    error = np.abs(small - reference).max(0) / np.abs(reference).max(0)
    return ReflectionCase(t, list(probe_xy), small, reference, error)


@dataclass
class LateTimeCase:
    steps: NDArray[np.int64]
    energy: NDArray[np.float64]
    """Total field energy per unit length (J/m), PML included."""


def late_time_case(n_steps: int = 30_000, backend: str = "numpy") -> LateTimeCase:
    """Run long after the pulse has left; the CPML must keep absorbing, never amplify."""
    dl = 0.05
    size = _centred_size(1.0, dl)
    sim = et.Simulation(
        size=(size, size, 0.0),
        grid=et.UniformGrid(dl=dl),
        boundary=et.PML(layers=12),
        sources=[
            et.PointSource(
                center=(0.0, 0.0, 0.0),
                component="Hz",
                pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.5),
            )
        ],
        run_time=1e-15,
        backend=backend,
    )
    solver = FDTDSolver(sim)
    area = (solver.grid.dx * UM) * (solver.grid.dy * UM)
    steps, energy = [], []
    for n in range(n_steps):
        solver.step()
        if n % 50 == 0:
            f = solver.fields()
            w = (
                0.5
                * EPSILON_0
                * (np.sum(f["Ex"].astype(float) ** 2) + np.sum(f["Ey"].astype(float) ** 2))
            )
            w += 0.5 * MU_0 * np.sum(f["Hz"].astype(float) ** 2)
            steps.append(n)
            energy.append(w * area)
    return LateTimeCase(np.array(steps), np.array(energy))


@dataclass
class GreenCase:
    """Hz from a magnetic line source vs the analytic 2D Green's function."""

    wavelengths: NDArray[np.float64]
    radius: float
    hz_measured: NDArray[np.complex128]
    hz_analytic: NDArray[np.complex128]


def green_function_case(
    dl: float = 0.05, radius: float = 3.0, backend: str = "numpy", precision: str = "single"
) -> GreenCase:
    """Hz(r, ω) = −(ωε0/4) K̂(ω) H0⁽¹⁾(k̃ r) for M_z = K(t) δ²(r) (time convention e^(−iωt)).

    K̂ is the DFT of the injected samples K(nΔt) (the same sum the monitor uses), and
    k̃ is the Yee wavenumber along the axis, so what is compared is the source
    normalisation 1/(ΔxΔy), the Δt in the DFT and every sign convention.
    """
    wavelengths = np.linspace(1.3, 1.8, 11)
    pulse = et.GaussianPulse(wavelength=1.55, bandwidth=0.5, amplitude=1.0)
    size = _centred_size(radius + 1.5, dl)
    m = round(radius / dl)
    sim = et.Simulation(
        size=(size, size, 0.0),
        grid=et.UniformGrid(dl=dl),
        boundary=et.PML(layers=12),
        sources=[et.PointSource(center=(0.0, 0.0, 0.0), component="Hz", pulse=pulse)],
        monitors=[
            et.DFTMonitor(
                name="probe", center=(m * dl, 0.0, 0.0), wavelengths=wavelengths, components=("Hz",)
            )
        ],
        run_time=250e-15,
        backend=backend,
        precision=precision,
    )
    result = sim.run()
    grid = result.grid
    t = np.arange(result.metadata["n_steps"]) * grid.dt  # M is sampled at nΔt
    omega = 2 * np.pi * et.C_0 / wavelengths
    k_hat = (pulse_signal(pulse, t)[None, :] * np.exp(1j * omega[:, None] * t[None, :])).sum(1)
    k_hat *= grid.dt
    v = numerical_phase_velocity(wavelengths, grid, angle=0.0)
    k_yee = 2 * np.pi / (wavelengths * UM) / v  # Yee wavenumber along x, 1/m
    analytic = -(omega * EPSILON_0 / 4.0) * k_hat * hankel1(0, k_yee * m * dl * UM)
    measured = np.asarray(result["probe"]["Hz"].values, dtype=np.complex128)
    return GreenCase(wavelengths, m * dl, measured, analytic)
