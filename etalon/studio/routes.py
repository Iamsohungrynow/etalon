"""U1's routes: templates, spec, jobs, results, and the 501 stubs (plan-u1 §13).

Binary arrays (§13.1) are ``application/octet-stream``; their headers and the
WebSocket messages are typed in ``contract.py``. Every solver run, spec capture
and calibration happens in a child process; the server itself only reads
models, grids and files.
"""

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from etalon.core.simulation import Simulation
from etalon.grid.materials import permittivity_on_nodes
from etalon.studio import editor, templates
from etalon.studio.binary import MEDIA_TYPE, finite_range, node_extent, pack
from etalon.studio.capture import run_child
from etalon.studio.contract import (
    AlreadyRunning,
    Calibration,
    Cancelling,
    CreateSimulation,
    JobStarted,
    NotImplementedBody,
    PermittivityHeader,
    Quantity,
    ResultMeta,
    ScriptError,
    SimulationSpec,
    Spectra,
    Template,
)
from etalon.studio.errors import ApiError, ModelError, StudioError
from etalon.studio.preview import (
    build_estimate,
    build_preview,
    build_warnings,
    memory_bytes,
    run_backend,
    solver_grid,
)
from etalon.studio.results import (
    ArrayCache,
    field_slice,
    parse_result_id,
    read_meta,
    result_meta,
    run_dir,
    spectra,
)
from etalon.studio.workspace import SimulationRow, find_script, row_for

if TYPE_CHECKING:
    from etalon.studio.server import StudioState

BINARY_RESPONSE: dict[str, Any] = {
    "description": "A binary float32 array with a JSON header (plan-u1 §13.1)",
    "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
}
SUBPROTOCOL = "etalon.v1"
CALIBRATION_SECONDS = 8.0
CALIBRATION_TIMEOUT_S = 180.0


def _error(description: str, model: type[Any] = ApiError) -> dict[str, Any]:
    return {"model": model, "description": description}


def not_implemented(endpoint: str, arrives_in: str) -> JSONResponse:
    body = NotImplementedBody(code="not_implemented", endpoint=endpoint, arrives_in=arrives_in)
    return JSONResponse(body.model_dump(), status_code=501)


def register_routes(app: FastAPI, state: "StudioState") -> None:
    """Add U1's routes to ``app``; they serve the workspace of ``state.settings``."""
    arrays = ArrayCache()

    def workspace() -> Path:
        return Path(state.settings.get().workspace)

    def script_for(sim_id: str) -> Path:
        script = find_script(workspace(), sim_id)
        if script is None:
            raise StudioError(404, "simulation_not_found", f"no simulation {sim_id!r}")
        return script

    def simulation_of(script: Path) -> tuple[str, str, Simulation]:
        """(sha256, stdout tail, Simulation) of the script, captured in a child process."""
        captured = state.specs.get(script, workspace())
        return captured.sha256, captured.stdout_tail, Simulation.model_validate(captured.spec)

    def has_gpu() -> bool:
        devices = state.probe.result().get("devices")
        return isinstance(devices, list) and len(devices) > 0

    # §13.2 Simulations and templates -------------------------------------------------
    @app.get("/api/templates", operation_id="listTemplates")
    def list_templates() -> list[Template]:
        return templates.list_templates()

    @app.post(
        "/api/simulations",
        operation_id="createSimulation",
        status_code=201,
        responses={
            409: _error("a script of that name exists (code exists)"),
            422: _error("the name is not [A-Za-z0-9_-]{1,64} (code bad_name)"),
        },
    )
    def create_simulation(body: CreateSimulation) -> SimulationRow:
        folder = workspace()
        script = templates.create_from_template(body.template, body.name, folder)
        return row_for(script, folder, state.jobs.running())

    @app.get(
        "/api/simulations/{id}/spec",
        operation_id="getSpec",
        responses={
            404: _error("no simulation with this id"),
            422: _error("the script failed, timed out or defines no Simulation", ScriptError),
        },
    )
    def get_spec(id: str) -> SimulationSpec:
        sha, stdout_tail, sim = simulation_of(script_for(id))
        grid = solver_grid(sim)
        estimate = memory = None
        if grid is not None:
            settings = state.settings.get()
            backend = run_backend(settings.backend, sim.backend, has_gpu())
            estimate = build_estimate(sim, grid, state.throughput, backend)
            memory = memory_bytes(sim, grid)
        return SimulationSpec(
            script_sha256=sha,
            spec=sim.model_dump(mode="json"),
            preview=build_preview(sim, grid),
            estimate=estimate,
            warnings=build_warnings(sim, grid, memory),
            stdout_tail=stdout_tail,
        )

    @app.get(
        "/api/simulations/{id}/permittivity",
        operation_id="getPermittivity",
        response_class=Response,
        responses={
            200: BINARY_RESPONSE,
            404: _error("no simulation with this id"),
            409: _error("the solver cannot grid this simulation yet (code unsupported)"),
            422: _error("the script failed, timed out or defines no Simulation", ScriptError),
        },
    )
    def get_permittivity(id: str, component: Literal["Ex", "Ey"] = "Ex") -> Response:
        _, _, sim = simulation_of(script_for(id))
        grid = solver_grid(sim)
        if grid is None:
            raise StudioError(409, "unsupported", "this build of the solver cannot grid it")
        eps = np.asarray(permittivity_on_nodes(sim, grid)[component], dtype=np.float32)
        x, y = grid.coords(component)
        low, high = finite_range(eps)
        header = PermittivityHeader(
            shape=(int(eps.shape[0]), int(eps.shape[1])),
            extent=node_extent(x, y),
            min=low,
            max=high,
            component=component,
            unit="1",
            pml_cells=grid.pml_layers,
        )
        return Response(pack(header, eps), media_type=MEDIA_TYPE)

    @app.post(
        "/api/simulations/{id}/open",
        operation_id="openInEditor",
        status_code=204,
        response_class=Response,
        responses={
            404: _error("no simulation with this id"),
            500: _error("the OS could not open an editor (code open_failed)"),
        },
    )
    def open_in_editor(id: str) -> Response:
        script = script_for(id)
        try:
            editor.open_in_editor(script)
        except (OSError, subprocess.SubprocessError) as error:
            raise StudioError(500, "open_failed", str(error)) from None
        return Response(status_code=204)

    @app.post(
        "/api/calibrate",
        operation_id="calibrate",
        responses={500: _error("the measurement failed (code calibration_failed)")},
    )
    def calibrate() -> Calibration:
        setting = state.settings.get().backend
        backend = run_backend(setting, "auto", has_gpu())
        solver_backend = "cuda" if backend.startswith("cuda:") else "numpy"
        device = backend.split(":")[1] if backend.startswith("cuda:") else "none"
        result, output, timed_out = run_child(
            ["calibrate", solver_backend, device, str(CALIBRATION_SECONDS)],
            workspace(),
            CALIBRATION_TIMEOUT_S,
        )
        if result is None or timed_out:
            tail = output.strip().splitlines()[-1:] or ["no output"]
            raise StudioError(500, "calibration_failed", tail[0])
        calibration = Calibration.model_validate(result)
        state.throughput.record(
            "calibration", calibration.backend, calibration.device, calibration.cells_per_s
        )
        return calibration

    # §13.3 Jobs ----------------------------------------------------------------------
    @app.post(
        "/api/simulations/{id}/run",
        operation_id="runSimulation",
        status_code=202,
        responses={
            404: _error("no simulation with this id"),
            409: _error("a job is already running this simulation", AlreadyRunning),
        },
    )
    def run_simulation(id: str) -> JobStarted:
        script = script_for(id)
        running = state.jobs.running_for(id)
        if running is not None:
            raise ModelError(
                409,
                AlreadyRunning(
                    code="already_running",
                    message=f"job {running.job_id} is running this simulation",
                    job_id=running.job_id,
                ),
            )
        settings = state.settings.get()
        backend: str | None = None
        device: int | None = None
        if settings.backend == "cpu":
            backend = "numpy"
        elif settings.backend.startswith("cuda:"):
            backend, device = "cuda", int(settings.backend.split(":")[1])
        job = state.jobs.start(
            script,
            workspace(),
            id,
            hashlib.sha256(script.read_bytes()).hexdigest(),
            backend,
            device,
            settings.live_snapshots,
        )
        return JobStarted(job_id=job.job_id, result_id=job.result_id)

    @app.delete(
        "/api/jobs/{job_id}",
        operation_id="cancelJob",
        status_code=202,
        responses={
            404: _error("no job with this id"),
            409: _error("the job has already finished (code not_running)"),
        },
    )
    def cancel_job(job_id: str) -> Cancelling:
        job = state.jobs.get(job_id)
        if job is None:
            raise StudioError(404, "job_not_found", f"no job {job_id!r}")
        if not job.running:
            raise StudioError(409, "not_running", f"job {job_id} has finished")
        state.jobs.cancel(job)
        return Cancelling(status="cancelling")

    @app.websocket("/api/jobs/{job_id}")
    async def job_socket(websocket: WebSocket, job_id: str) -> None:
        job = state.jobs.get(job_id)
        if job is None:
            await websocket.close(code=1008, reason="job_not_found")
            return
        offered = websocket.scope.get("subprotocols", [])
        await websocket.accept(subprotocol=SUBPROTOCOL if SUBPROTOCOL in offered else None)
        subscriber = job.subscribe(asyncio.get_running_loop())
        try:
            while True:
                message = await subscriber.queue.get()
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                    continue
                await websocket.send_text(json.dumps(message, allow_nan=False))
                if message["type"] == "done":
                    break
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            pass  # the browser went away
        finally:
            job.unsubscribe(subscriber)

    # §13.4 Results -------------------------------------------------------------------
    def finished_run(result_id: str) -> tuple[Path, Path, dict[str, Any]]:
        """(script, run folder, meta.json) of a run that left monitor data."""
        sim_id, stamp = parse_result_id(result_id)
        script = find_script(workspace(), sim_id)
        if script is None:
            raise StudioError(404, "result_not_found", f"no result {result_id!r}")
        job = state.jobs.by_result(result_id)
        if job is not None and job.running:
            raise StudioError(409, "running", f"run {result_id} is still running")
        folder = run_dir(script, stamp)
        meta = read_meta(folder)
        if meta is None:
            raise StudioError(404, "result_not_found", f"no result {result_id!r}")
        if not meta.get("has_result") or not (folder / "result.npz").exists():
            raise StudioError(404, "no_result", f"run {result_id} left no monitor data")
        if meta["status"] == "running":
            # A run killed after saving its data, with no job left to finish it.
            meta = {**meta, "status": "cancelled", "finished_at": meta["started_at"]}
        return script, folder, meta

    @app.get(
        "/api/results/{id}",
        operation_id="getResult",
        responses={
            404: _error("no result with this id, or the run left no data (code no_result)"),
            409: _error("the run is still running (code running)"),
        },
    )
    def get_result(id: str) -> ResultMeta:
        script, _, meta = finished_run(id)
        return result_meta(script, meta)

    @app.get(
        "/api/results/{id}/fields/{monitor}",
        operation_id="getField",
        response_class=Response,
        responses={
            200: BINARY_RESPONSE,
            404: _error("no such result, monitor, component or wavelength index"),
            409: _error("a point monitor has no field slice (code point_monitor)"),
        },
    )
    def get_field(
        id: str,
        monitor: str,
        component: str | None = None,
        quantity: Quantity = "abs",
        wavelength_index: int = 0,
    ) -> Response:
        _, folder, meta = finished_run(id)
        data = field_slice(folder, meta, arrays, monitor, component, quantity, wavelength_index)
        return Response(data, media_type=MEDIA_TYPE)

    @app.get(
        "/api/results/{id}/spectra/{monitor}",
        operation_id="getSpectra",
        responses={
            404: _error("no such result or monitor"),
            409: _error("only point monitors have spectra (code not_point_monitor)"),
        },
    )
    def get_spectra(id: str, monitor: str) -> Spectra:
        _, folder, meta = finished_run(id)
        return spectra(folder, meta, arrays, monitor)

    # §13.5 Still 501 -----------------------------------------------------------------
    stub: dict[str, Any] = {"status_code": 501, "response_model": NotImplementedBody}

    @app.put("/api/simulations/{id}/params", operation_id="putParams", **stub)
    def put_params(id: str) -> JSONResponse:
        return not_implemented("PUT /api/simulations/{id}/params", "U1 + et.param")

    @app.get("/api/results/{id}/s-matrix", operation_id="getSMatrix", **stub)
    def get_s_matrix(id: str) -> JSONResponse:
        return not_implemented("GET /api/results/{id}/s-matrix", "M2")

    @app.get("/api/results/{id}/modes/{monitor}", operation_id="getModes", **stub)
    def get_modes(id: str, monitor: str) -> JSONResponse:
        return not_implemented("GET /api/results/{id}/modes/{monitor}", "M1")

    @app.post("/api/modes/solve", operation_id="solveModes", **stub)
    def solve_modes() -> JSONResponse:
        return not_implemented("POST /api/modes/solve", "M1")

    @app.get("/api/validation/latest", operation_id="getValidationLatest", **stub)
    def get_validation_latest() -> JSONResponse:
        return not_implemented("GET /api/validation/latest", "U4")

    @app.post("/api/validation/run", operation_id="runValidation", **stub)
    def run_validation() -> JSONResponse:
        return not_implemented("POST /api/validation/run", "U4")
