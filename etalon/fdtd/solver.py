"""The 2D TE time-stepping loop, independent of the backend.

One step n (E^n, H^(n−½) → E^(n+1), H^(n+½)):

    1. H update; magnetic sources injected with M sampled at t = nΔt
    2. DFT of H with t = (n + ½)Δt
    3. E update; electric sources injected with J sampled at t = (n + ½)Δt
    4. DFT of E with t = (n + 1)Δt

All host-side setup is float64 and SI; arrays are cast once to the run's
precision and moved to the backend's device.
"""

import time
from typing import Any

import numpy as np

from etalon import __version__
from etalon.core.simulation import Simulation
from etalon.fdtd.backends import get_backend
from etalon.fdtd.capabilities import check_supported
from etalon.fdtd.cpml import cpml_axis
from etalon.fdtd.dft import ComponentSampling, dft_phasors, monitor_samplings
from etalon.fdtd.sources import point_injection
from etalon.fdtd.state import build_te_state
from etalon.grid.materials import permittivity_on_nodes
from etalon.grid.yee import build_yee_grid
from etalon.io.result import SimulationResult, monitor_dataarray

# Upper bound on the phasor table uploaded at once (time steps × frequencies).
_PHASOR_TABLE_ENTRIES = 1 << 22


class _MonitorAccumulator:
    """DFT state of one monitor component: device accumulator plus phasor tables."""

    def __init__(self, sampling: ComponentSampling, backend: Any, complex_dtype: Any) -> None:
        self.sampling = sampling
        self.index = backend.to_device(sampling.flat_index)
        n_f = sampling.wavelengths.size
        self.acc = backend.to_device(np.zeros((n_f, sampling.flat_index.size), complex_dtype))
        self.chunk = max(1, _PHASOR_TABLE_ENTRIES // n_f)
        self.table_start = -1
        self.table: Any = None


class FDTDSolver:
    """Builds the state of a simulation and advances it; ``run()`` does everything.

    Tests use ``step()`` and ``fields()`` directly to look inside a run.
    """

    def __init__(self, sim: Simulation) -> None:
        check_supported(sim)
        self.sim = sim
        self.grid = build_yee_grid(sim)
        self.n_steps = self.grid.n_steps(sim.run_time)
        self.backend = get_backend(sim.backend, sim.precision)
        self.real = np.float32 if sim.precision == "single" else np.float64
        self.complex = np.complex64 if sim.precision == "single" else np.complex128

        grid = self.grid
        eps_r = permittivity_on_nodes(sim, grid)
        background = sim.medium.permittivity
        cpml_x = cpml_axis(grid.nx, grid.dx, grid.dt, sim.boundary, background)
        cpml_y = cpml_axis(grid.ny, grid.dy, grid.dt, sim.boundary, background)
        self.state = build_te_state(grid, eps_r, cpml_x, cpml_y, self.real, self.backend.to_device)

        self.injections = [point_injection(source, grid, eps_r) for source in sim.sources]
        self._injection_index = [
            (self.backend.to_device(inj.i), self.backend.to_device(inj.j))
            for inj in self.injections
        ]
        self.monitors = [
            _MonitorAccumulator(sampling, self.backend, self.complex)
            for monitor in sim.monitors
            for sampling in monitor_samplings(monitor, grid)
        ]
        self.n = 0

    def _inject(self, magnetic: bool) -> None:
        for inj, (i, j) in zip(self.injections, self._injection_index, strict=True):
            if inj.is_magnetic != magnetic:
                continue
            delta = self.backend.to_device(inj.delta(self.n, self.grid.dt).astype(self.real))
            field = getattr(self.state, inj.component.lower())
            field[i, j] -= delta

    def _phasor_rows(self, mon: _MonitorAccumulator) -> tuple[Any, Any]:
        """Phasors for H at (n+½)Δt and E at (n+1)Δt, from a table refilled every chunk."""
        if mon.table is None or self.n >= mon.table_start + mon.chunk:
            mon.table_start = self.n
            steps = np.arange(self.n, self.n + mon.chunk, dtype=np.float64)
            f = mon.sampling.frequencies
            dt = self.grid.dt
            table_h = dft_phasors(f, (steps + 0.5) * dt, dt).astype(self.complex)
            table_e = dft_phasors(f, (steps + 1.0) * dt, dt).astype(self.complex)
            mon.table = (self.backend.to_device(table_h), self.backend.to_device(table_e))
        row = self.n - mon.table_start
        return mon.table[0][row], mon.table[1][row]

    def _accumulate(self, magnetic: bool) -> None:
        for mon in self.monitors:
            if mon.sampling.is_magnetic != magnetic:
                continue
            ph_h, ph_e = self._phasor_rows(mon)
            field = getattr(self.state, mon.sampling.component.lower())
            self.backend.accumulate_dft(mon.acc, field, mon.index, ph_h if magnetic else ph_e)

    def step(self) -> None:
        """Advance one time step (see the module docstring for the order)."""
        self.backend.update_h_te(self.state)
        self._inject(magnetic=True)
        self._accumulate(magnetic=True)
        self.backend.update_e_te(self.state)
        self._inject(magnetic=False)
        self._accumulate(magnetic=False)
        self.n += 1

    def fields(self) -> dict[str, np.ndarray]:
        """Host copies of Ex, Ey, Hz (E at nΔt, H at (n−½)Δt)."""
        s = self.state
        return {name: self.backend.to_host(getattr(s, name.lower())) for name in ("Ex", "Ey", "Hz")}

    def result(self, wall_time: float = float("nan")) -> SimulationResult:
        data: dict[str, dict[str, Any]] = {monitor.name: {} for monitor in self.sim.monitors}
        for mon in self.monitors:
            acc = self.backend.to_host(mon.acc)
            data[mon.sampling.monitor][mon.sampling.component] = monitor_dataarray(
                mon.sampling, acc, self.grid.z
            )
        metadata = {
            "etalon_version": __version__,
            "backend": self.backend.name,
            "device": self.backend.device,
            "precision": self.sim.precision,
            "n_steps": self.n,
            "dt_s": self.grid.dt,
            "grid_cells": (self.grid.nx, self.grid.ny),
            "wall_time_s": wall_time,
            "cell_updates_per_s": self.grid.n_cells * self.n / wall_time if wall_time > 0 else None,
        }
        return SimulationResult(self.sim, self.grid, data, metadata)

    def run(self) -> SimulationResult:
        start = time.perf_counter()
        while self.n < self.n_steps:
            self.step()
        self.backend.synchronize()
        return self.result(time.perf_counter() - start)


def run(sim: Simulation) -> SimulationResult:
    """Run a simulation to ``run_time`` and collect its monitors."""
    return FDTDSolver(sim).run()
