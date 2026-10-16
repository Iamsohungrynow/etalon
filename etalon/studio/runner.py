"""What Studio runs in child processes: never in the server itself (plan-u1 §2).

Studio does not change solver code. It runs the user's script and replaces
``Simulation.run`` at runtime, in the child process only:

- **spec**: ``python -P -m etalon.studio.runner spec OUT SCRIPT``. ``run()``
  records the simulation and stops the script; a script that never calls
  ``run()`` falls back to the first module-level Simulation it defines. The
  result (``Simulation.model_dump(mode="json")`` or the error) goes to OUT as JSON;
  what the script prints goes to stdout, which the server keeps as the tail.
- **calibrate**: ``python -P -m etalon.studio.runner calibrate OUT BACKEND DEVICE SECONDS``
  times ``etalon.validation.throughput`` for about SECONDS.
- **run**: ``run_job`` is the target of a ``multiprocessing`` spawn child. The
  first ``run()`` steps the public ``FDTDSolver`` itself, sending progress,
  snapshots and log lines to the server, and the script then carries on with the
  real ``SimulationResult``, exactly as if it had run normally.

Everything here imports the solver lazily: the server imports this module for
``run_job``'s name, and must not load xarray, SciPy or CuPy.
"""

import contextlib
import io
import json
import logging
import math
import os
import runpy
import sys
import threading
import time
import traceback
import warnings
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import numpy as np

# Imported here, before the user's script loads xarray or CuPy: pydantic reads the
# models' attribute docstrings through ``inspect``, which slows down by seconds once
# thousands of modules are loaded.
from etalon.studio.binary import finite_range, node_extent, pack
from etalon.studio.contract import MonitorGeometry, SnapshotHeader

SNAPSHOT_MAX_NODES = 256
"""Live snapshots are downsampled to at most this many nodes along each axis."""
PROGRESS_INTERVAL_S = 0.25
"""At most 4 progress messages per second."""
SNAPSHOT_INTERVAL_S = 0.1
"""At most 10 snapshots per second."""
CANCEL_CHECK_S = 0.05
HEARTBEAT_S = 1.0
"""How often a running job rewrites status.json."""
MAX_LINE = 2000
"""Longer printed lines are cut, so one runaway print cannot flood the log."""


class _Captured(BaseException):
    """Raised by the patched ``run()`` in spec mode, to stop the script there."""

    def __init__(self, simulation: Any) -> None:
        super().__init__("captured")
        self.simulation = simulation


class _Cancelled(BaseException):
    """Raised by the patched ``run()`` after a cancelled run saved its partial data."""


class NumericalInstability(FloatingPointError):
    """The fields stopped being finite: the run diverged."""


# Running a script -----------------------------------------------------------------------
def run_script(script: Path) -> dict[str, Any]:
    """Run ``script`` as ``__main__`` the way ``python script.py`` would, and return its globals."""
    script = script.resolve()
    sys.argv = [str(script)]
    sys.path.insert(0, str(script.parent))
    return runpy.run_path(str(script), run_name="__main__")


def script_failure(error: BaseException, script: Path) -> dict[str, Any]:
    """``{message, traceback, line}`` of an exception, the traceback starting in the script."""
    script_name = os.path.normcase(str(script.resolve()))
    tb: TracebackType | None = error.__traceback__
    while tb is not None and os.path.normcase(tb.tb_frame.f_code.co_filename) != script_name:
        tb = tb.tb_next
    line: int | None = None
    walker = tb
    while walker is not None:
        if os.path.normcase(walker.tb_frame.f_code.co_filename) == script_name:
            line = walker.tb_lineno
        walker = walker.tb_next
    if isinstance(error, SyntaxError) and error.filename is not None:
        if os.path.normcase(str(Path(error.filename).resolve())) == script_name:
            line = error.lineno
    text = "".join(traceback.format_exception(type(error), error, tb))
    return {"message": str(error), "traceback": text, "line": line}


def _first_simulation(namespace: dict[str, Any]) -> Any:
    from etalon.core.simulation import Simulation

    for value in namespace.values():
        if isinstance(value, Simulation):
            return value
    return None


# Spec mode --------------------------------------------------------------------------------
def capture_spec(script: Path) -> dict[str, Any]:
    """Run ``script`` up to its first ``run()``; the simulation's JSON, or why there is none."""
    from etalon.core.simulation import Simulation

    def captured_run(self: Simulation) -> Any:
        raise _Captured(self)

    Simulation.run = captured_run  # type: ignore[method-assign]
    try:
        namespace = run_script(script)
    except _Captured as captured:
        simulation = captured.simulation
    except SystemExit as error:
        if error.code not in (None, 0):
            return {"ok": False, "code": "script_error", **script_failure(error, script)}
        simulation = None
    except BaseException as error:
        return {"ok": False, "code": "script_error", **script_failure(error, script)}
    else:
        simulation = _first_simulation(namespace)
    if simulation is None:
        return {
            "ok": False,
            "code": "no_simulation",
            "message": "",
            "traceback": "",
            "line": None,
        }
    return {"ok": True, "spec": simulation.model_dump(mode="json")}


# Calibration ------------------------------------------------------------------------------
def calibrate(backend: str, device: int | None, seconds: float) -> dict[str, Any]:
    """Cells per second of ``backend`` ("numpy" or "cuda") over about ``seconds``."""
    from etalon.validation.throughput import measure_throughput

    if backend == "cuda" and device is not None:
        import cupy

        cupy.cuda.Device(device).use()
    region = 2000 if backend == "cuda" else 500
    trial = measure_throughput(region_cells=region, steps=10, backend=backend, warmup=5)
    n_cells = trial.cells[0] * trial.cells[1]
    steps = int(seconds * trial.cell_updates_per_s / n_cells)
    steps = min(max(steps, 20), 200_000)
    result = measure_throughput(region_cells=region, steps=steps, backend=backend, warmup=5)
    label, name = backend_label(result.backend, result.device)
    return {"cells_per_s": result.cell_updates_per_s, "backend": label, "device": name}


def backend_label(backend: str, device: str) -> tuple[str, str]:
    """Studio's ("cuda:0", "NVIDIA ...") or ("cpu", CPU model) for a solver backend."""
    if backend == "cuda":
        label, _, name = device.partition(" ")
        return label, name or label
    return "cpu", cpu_name()


def cpu_name() -> str:
    """The CPU model, as the OS names it."""
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            with key:
                value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return str(value).strip()
        except OSError:
            pass
    elif sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    import platform

    return platform.processor() or platform.machine() or "CPU"


# Run mode: the child's side of a job ----------------------------------------------------------
def write_json_atomically(path: Path, data: dict[str, Any]) -> None:
    """Write through a temporary file; retry the rename while a reader holds the file (Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for attempt in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.01)


class _LineStream(io.TextIOBase):
    """A text stream that hands every complete line to ``sink(stream, line)``."""

    def __init__(self, stream: str, sink: Callable[[str, str], None]) -> None:
        self._stream = stream
        self._sink = sink
        self._pending = ""
        self._lock = threading.Lock()

    encoding = "utf-8"

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        with self._lock:
            self._pending += text
            *lines, self._pending = self._pending.split("\n")
        for line in lines:
            self._sink(self._stream, line.rstrip("\r"))
        return len(text)

    def flush(self) -> None:
        pass

    def close_line(self) -> None:
        """Send what is left without a newline."""
        with self._lock:
            rest, self._pending = self._pending, ""
        if rest:
            self._sink(self._stream, rest)


class _LogHandler(logging.Handler):
    def __init__(self, sink: Callable[[str, str], None]) -> None:
        super().__init__(logging.INFO)
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink("etalon", self.format(record))


def field_energy(solver: Any) -> float:
    """Discrete field energy per unit length, J/m (plan-u1 §3), computed on the device.

        W = ½ ΔxΔy Σ (ε0 εr E² + μ0 Hz²)

    ε0 εr comes from the solver's own coefficients, cb = Δt/(ε0 εr) at the Ex and Ey
    nodes, and μ0 = Δt/db. The sums run in float64 so float32 fields cannot overflow.
    """
    from etalon.constants import UM

    state = solver.state
    xp = solver.backend.xp
    dt = solver.grid.dt

    def weighted(field: Any, coefficient: Any) -> float:
        values = field.astype(xp.float64)
        return float(xp.sum(values * values / coefficient))

    hz = state.hz.astype(xp.float64)
    electric = dt * (weighted(state.ex, state.cb_ex) + weighted(state.ey, state.cb_ey))
    magnetic = dt / float(state.db) * float(xp.sum(hz * hz))
    cell_area = solver.grid.dx * UM * solver.grid.dy * UM
    return float(0.5 * cell_area * (electric + magnetic))


def downsample(field: Any, xp: Any, max_nodes: int = SNAPSHOT_MAX_NODES) -> tuple[Any, int, int]:
    """Block means of ``field`` with at most ``max_nodes`` per axis; returns (blocks, sx, sy)."""
    n_x, n_y = field.shape
    sx = max(1, math.ceil(n_x / max_nodes))
    sy = max(1, math.ceil(n_y / max_nodes))
    mx, my = n_x // sx, n_y // sy
    blocks = field[: mx * sx, : my * sy].reshape(mx, sx, my, sy).mean(axis=(1, 3))
    return blocks.astype(xp.float32), sx, sy


def snapshot_frame(solver: Any) -> bytes:
    """A §13.1 binary snapshot of Hz, downsampled on the device before the copy."""
    blocks, sx, sy = downsample(solver.state.hz, solver.backend.xp)
    data = np.asarray(solver.backend.to_host(blocks), dtype=np.float32)
    mx, my = data.shape
    x, y = solver.grid.coords("Hz")
    xb = x[: mx * sx].reshape(mx, sx).mean(axis=1)
    yb = y[: my * sy].reshape(my, sy).mean(axis=1)
    low, high = finite_range(data)
    header = SnapshotHeader(
        shape=(mx, my),
        extent=node_extent(xb, yb),
        min=low,
        max=high,
        component="Hz",
        unit="A/m",
        step=solver.n,
    )
    return pack(header, data)


def monitor_layout(sim: Any, result: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The arrays of ``result.npz`` and the monitor list of ``meta.json``.

    Keys: ``m<i>.<C>`` complex data shaped (n_x, n_y, n_wavelengths), with n = 1 along
    an interpolated axis; ``m<i>.<C>.x`` and ``.y`` its node coordinates (µm);
    ``m<i>.wavelengths`` (µm). ``i`` is the monitor's index in ``Simulation.monitors``.
    """
    arrays: dict[str, Any] = {}
    monitors = []
    for i, monitor in enumerate(sim.monitors):
        components = result[monitor.name]
        first: tuple[list[int], list[float]] | None = None
        for component, data_array in components.items():
            data = np.asarray(data_array.values)
            if "x" not in data_array.dims:
                data = data[np.newaxis, ...]
            if "y" not in data_array.dims:
                data = data[:, np.newaxis, ...]
            x = np.atleast_1d(np.asarray(data_array.coords["x"].values, dtype=np.float64))
            y = np.atleast_1d(np.asarray(data_array.coords["y"].values, dtype=np.float64))
            arrays[f"m{i}.{component}"] = data
            arrays[f"m{i}.{component}.x"] = x
            arrays[f"m{i}.{component}.y"] = y
            if first is None:
                first = (
                    [int(data.shape[0]), int(data.shape[1])],
                    [float(x[0]), float(x[-1]), float(y[0]), float(y[-1])],
                )
        arrays[f"m{i}.wavelengths"] = np.asarray(monitor.wavelengths, dtype=np.float64)
        geometry = monitor_geometry(monitor.size)
        point = geometry == "point"
        monitors.append(
            {
                "name": monitor.name,
                "index": i,
                "geometry": geometry,
                "components": list(components),
                "wavelengths_um": [float(w) for w in monitor.wavelengths],
                "shape": None if point or first is None else first[0],
                "extent": None if point or first is None else first[1],
            }
        )
    return arrays, monitors


def monitor_geometry(size: tuple[float, float, float]) -> MonitorGeometry:
    """How many axes of a monitor have size > 0: 0 point, 1 line, 2 plane, 3 box."""
    geometries: tuple[MonitorGeometry, ...] = ("point", "line", "plane", "box")
    return geometries[sum(1 for s in size if s > 0.0)]


def suggestion_for(error: BaseException) -> str | None:
    """The one-line suggestion the Run screen shows for a failure we recognise."""
    names = {cls.__name__ for cls in type(error).__mro__}
    if isinstance(error, MemoryError) or "OutOfMemoryError" in names:
        return "out_of_memory"
    if "cudaErrorMemoryAllocation" in str(error):
        return "out_of_memory"
    if isinstance(error, NumericalInstability):
        return "nan"
    if isinstance(error, NotImplementedError):
        return "unsupported"
    return None


class _Job:
    """State of one run inside the child: what goes to the server and to the run folder."""

    def __init__(self, params: dict[str, Any], queue: Any, cancel: Any) -> None:
        self.params = params
        self.queue = queue
        self.cancel = cancel
        self.run_dir = Path(params["run_dir"])
        self.status_path = Path(params["status_path"])
        self.started_at = params["started_at"]
        self.status: dict[str, Any] = {
            "status": "running",
            "started_at": params["started_at"],
            "script_sha256": params["script_sha256"],
            "last_run": params["stamp"],
            "last_result": params.get("previous_result"),
        }
        self.status_lock = threading.Lock()
        self.log_file = open(self.run_dir / "log.txt", "a", encoding="utf-8", newline="\n")
        self.log_lock = threading.Lock()
        self.meta: dict[str, Any] = {
            "result_id": params["result_id"],
            "simulation_id": params["sim_id"],
            "status": "running",
            "started_at": params["started_at"],
            "script_sha256": params["script_sha256"],
            "has_result": False,
        }
        self.has_result = False
        self.ran = False
        self.cancelled = False
        self.wall_time_s = 0.0
        self.cells_per_s = 0.0
        self._stop = threading.Event()

    # messages ---------------------------------------------------------------------------
    def send(self, message: dict[str, Any] | bytes) -> None:
        self.queue.put(message)

    def log(self, stream: str, line: str) -> None:
        line = line[:MAX_LINE]
        stamp = datetime.now(UTC).strftime("%H:%M:%S")
        with self.log_lock:
            self.log_file.write(f"{stamp} {stream:<6} {line}\n")
            self.log_file.flush()
        self.send({"type": "log", "stream": stream, "line": line})

    # status.json --------------------------------------------------------------------------
    def update_status(self, **fields: Any) -> None:
        with self.status_lock:
            self.status.update(fields)
            self.status["heartbeat_at"] = datetime.now(UTC).isoformat()
            write_json_atomically(self.status_path, self.status)

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_S):
            with contextlib.suppress(OSError):
                self.update_status()

    def start_heartbeat(self) -> None:
        threading.Thread(target=self._heartbeat, name="etalon-heartbeat", daemon=True).start()

    def stop_heartbeat(self) -> None:
        self._stop.set()

    # the patched run() ---------------------------------------------------------------------
    def studio_run(self, sim: Any) -> Any:
        from etalon.fdtd.solver import FDTDSolver
        from etalon.fdtd.solver import run as plain_run

        override = self.params.get("backend")
        if override is not None:
            sim = sim.model_copy(update={"backend": override})
        if self.ran:
            self.log("etalon", "run() called again: this run is not shown in Studio")
            return plain_run(sim)
        self.ran = True
        device = self.params.get("device")
        if sim.backend == "cuda" and device is not None:
            import cupy

            cupy.cuda.Device(device).use()
        for line in sim.summary().splitlines():
            self.log("etalon", line)
        solver = FDTDSolver(sim)
        grid = solver.grid
        label, device_name = backend_label(solver.backend.name, solver.backend.device)
        snapshots = bool(self.params.get("live_snapshots")) or solver.backend.name == "cuda"
        total = solver.n_steps
        self.meta.update(
            {
                "etalon_version": _etalon_version(),
                "backend": label,
                "device": device_name,
                "precision": sim.precision,
                "grid": {"nx": grid.nx, "ny": grid.ny, "dx": grid.dx, "dy": grid.dy},
                "dt_s": grid.dt,
                "spec": sim.model_dump(mode="json"),
            }
        )
        self.update_status(
            backend=label, device=device_name, cells=grid.n_cells, step=0, total_steps=total
        )
        self.send(
            {
                "type": "started",
                "total": total,
                "grid": [grid.nx, grid.ny],
                "dt_s": grid.dt,
                "backend": label,
                "device": device_name,
                "snapshots": snapshots,
            }
        )
        self.log(
            "etalon", f"backend {label} {device_name}; snapshots {'on' if snapshots else 'off'}"
        )

        start = time.perf_counter()
        last_check = last_progress = last_snapshot = start

        def progress(now: float) -> float:
            energy = field_energy(solver)
            elapsed = now - start
            rate = solver.n / elapsed if elapsed > 0 else 0.0
            self.cells_per_s = grid.n_cells * rate
            eta = (total - solver.n) / rate if rate > 0 else 0.0
            self.send(
                {
                    "type": "progress",
                    "step": solver.n,
                    "total": total,
                    "elapsed_s": elapsed,
                    "eta_s": eta,
                    "cells_per_s": self.cells_per_s,
                    "energy": energy if math.isfinite(energy) else 0.0,
                }
            )
            with contextlib.suppress(OSError):
                self.update_status(step=solver.n, eta_s=eta)
            if not math.isfinite(energy):
                raise NumericalInstability(
                    f"the fields stopped being finite at step {solver.n} of {total}"
                )
            return energy

        try:
            while solver.n < total:
                solver.step()
                now = time.perf_counter()
                if now - last_check >= CANCEL_CHECK_S:
                    last_check = now
                    if self.cancel.is_set():
                        self.cancelled = True
                        break
                if now - last_progress >= PROGRESS_INTERVAL_S:
                    last_progress = now
                    progress(now)
                if snapshots and now - last_snapshot >= SNAPSHOT_INTERVAL_S:
                    last_snapshot = now
                    self.send(snapshot_frame(solver))
        except KeyboardInterrupt:
            self.cancelled = True
        solver.backend.synchronize()
        now = time.perf_counter()
        self.wall_time_s = now - start
        progress(now)
        if snapshots:
            self.send(snapshot_frame(solver))
        result = solver.result(self.wall_time_s)
        self._save(sim, result, solver.n)
        if self.cancelled:
            self.log("etalon", f"cancelled at step {solver.n} of {total}; partial data saved")
            raise _Cancelled()
        return result

    def _save(self, sim: Any, result: Any, steps: int) -> None:
        arrays, monitors = monitor_layout(sim, result)
        tmp = self.run_dir / "result.tmp.npz"
        np.savez(tmp, **arrays)
        os.replace(tmp, self.run_dir / "result.npz")
        self.has_result = True
        self.meta.update(
            {
                "steps": steps,
                "wall_time_s": self.wall_time_s,
                "cells_per_s": self.cells_per_s,
                "monitors": monitors,
                "has_result": True,
            }
        )
        # Written now as well, so the data stays readable if the process is killed later.
        write_json_atomically(self.run_dir / "meta.json", self.meta)
        self.update_status(last_result=self.params["stamp"])

    # the end ----------------------------------------------------------------------------------
    def finish(self, status: str, error: dict[str, Any] | None, suggestion: str | None) -> None:
        self.stop_heartbeat()
        finished_at = datetime.now(UTC).isoformat()
        self.meta.update(
            {
                "status": status,
                "finished_at": finished_at,
                "has_result": self.has_result,
                "error": error,
                "suggestion": suggestion,
            }
        )
        write_json_atomically(self.run_dir / "meta.json", self.meta)
        self.update_status(
            status=status,
            finished_at=finished_at,
            wall_time_s=self.wall_time_s if self.ran else None,
            eta_s=None,
        )
        self.send(
            {
                "type": "done",
                "status": status,
                "result_id": self.params["result_id"] if self.has_result else None,
                "error": error,
                "suggestion": suggestion,
            }
        )
        self.log_file.close()


def _etalon_version() -> str:
    from etalon import __version__

    return __version__


def run_job(params: dict[str, Any], queue: Any, cancel: Any) -> None:
    """Target of the job's spawn child: run the script with Studio's ``run()``.

    ``params``: script, workspace, run_dir, status_path, sim_id, result_id, stamp,
    started_at, script_sha256, previous_result, backend ("numpy", "cuda" or None to
    keep the script's), device (CUDA index or None), live_snapshots.
    """
    os.environ["MPLBACKEND"] = "Agg"
    # CuPy cannot name a CUDA_PATH when the toolkit comes from NVIDIA's wheels; it still works.
    warnings.filterwarnings("ignore", "CUDA path could not be detected")
    job = _Job(params, queue, cancel)
    stdout = _LineStream("stdout", job.log)
    stderr = _LineStream("stderr", job.log)
    sys.stdout, sys.stderr = stdout, stderr
    logging.getLogger("etalon").addHandler(_LogHandler(job.log))
    logging.getLogger("etalon").setLevel(logging.INFO)
    job.update_status()
    job.start_heartbeat()
    script = Path(params["script"])
    os.chdir(params["workspace"])

    from etalon.core.simulation import Simulation

    def studio_run(self: Simulation) -> Any:
        return job.studio_run(self)

    Simulation.run = studio_run  # type: ignore[method-assign]
    status, error, suggestion = "done", None, None
    try:
        run_script(script)
    except _Cancelled:
        status = "cancelled"
    except KeyboardInterrupt:
        status = "cancelled"
    except SystemExit as exit_:
        if exit_.code not in (None, 0):
            status, error = "failed", script_failure(exit_, script)
    except BaseException as failure:
        status, error, suggestion = (
            "failed",
            script_failure(failure, script),
            suggestion_for(failure),
        )
        for line in error["traceback"].rstrip("\n").splitlines():
            job.log("stderr", line)
    finally:
        stdout.close_line()
        stderr.close_line()
    if status == "done" and not job.ran:
        job.log("etalon", "the script finished without calling run()")
    job.finish(status, error, suggestion)


# Command line (spec and calibrate) ---------------------------------------------------------
def main(argv: list[str]) -> int:
    mode, out = argv[0], Path(argv[1])
    if mode == "spec":
        os.environ["MPLBACKEND"] = "Agg"
        result = capture_spec(Path(argv[2]))
    elif mode == "calibrate":
        device = None if argv[3] == "none" else int(argv[3])
        result = calibrate(argv[2], device, float(argv[4]))
    else:
        raise SystemExit(f"unknown mode {mode!r}")
    sys.stdout.flush()
    out.write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
