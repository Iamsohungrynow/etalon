"""U1's HTTP routes: templates, spec, jobs, results, and the 501 stubs (plan-u1 §13).

Binary arrays (§13.1) are ``application/octet-stream``; their headers and the
WebSocket messages are typed in ``contract.py``.
"""

from typing import TYPE_CHECKING, Any, Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from etalon.studio.contract import (
    AlreadyRunning,
    Calibration,
    Cancelling,
    CreateSimulation,
    JobStarted,
    NotImplementedBody,
    Quantity,
    ResultMeta,
    ScriptError,
    SimulationSpec,
    Spectra,
    Template,
)
from etalon.studio.errors import ApiError
from etalon.studio.workspace import SimulationRow

if TYPE_CHECKING:
    from etalon.studio.server import StudioState

BINARY_RESPONSE: dict[str, Any] = {
    "description": "A binary float32 array with a JSON header (plan-u1 §13.1)",
    "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
}


def _error(description: str, model: type[Any] = ApiError) -> dict[str, Any]:
    return {"model": model, "description": description}


def not_implemented(endpoint: str, arrives_in: str) -> JSONResponse:
    body = NotImplementedBody(code="not_implemented", endpoint=endpoint, arrives_in=arrives_in)
    return JSONResponse(body.model_dump(), status_code=501)


def register_routes(app: FastAPI, state: "StudioState") -> None:
    """Add U1's routes to ``app``; they serve the workspace of ``state.settings``."""

    # §13.2 Simulations and templates -------------------------------------------------
    @app.get("/api/templates", operation_id="listTemplates")
    def list_templates() -> list[Template]:
        return []

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
        return _pending("POST /api/simulations")  # type: ignore[return-value]

    @app.get(
        "/api/simulations/{id}/spec",
        operation_id="getSpec",
        responses={
            404: _error("no simulation with this id"),
            422: _error("the script failed, timed out or defines no Simulation", ScriptError),
        },
    )
    def get_spec(id: str) -> SimulationSpec:
        return _pending("GET /api/simulations/{id}/spec")  # type: ignore[return-value]

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
        return _pending("GET /api/simulations/{id}/permittivity")

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
        return _pending("POST /api/simulations/{id}/open")

    @app.post(
        "/api/calibrate",
        operation_id="calibrate",
        responses={500: _error("the measurement failed (code calibration_failed)")},
    )
    def calibrate() -> Calibration:
        return _pending("POST /api/calibrate")  # type: ignore[return-value]

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
        return _pending("POST /api/simulations/{id}/run")  # type: ignore[return-value]

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
        return _pending("DELETE /api/jobs/{job_id}")  # type: ignore[return-value]

    # §13.4 Results -------------------------------------------------------------------
    @app.get(
        "/api/results/{id}",
        operation_id="getResult",
        responses={
            404: _error("no result with this id, or the run left no data (code no_result)"),
            409: _error("the run is still running (code running)"),
        },
    )
    def get_result(id: str) -> ResultMeta:
        return _pending("GET /api/results/{id}")  # type: ignore[return-value]

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
        return _pending("GET /api/results/{id}/fields/{monitor}")

    @app.get(
        "/api/results/{id}/spectra/{monitor}",
        operation_id="getSpectra",
        responses={
            404: _error("no such result or monitor"),
            409: _error("only point monitors have spectra (code not_point_monitor)"),
        },
    )
    def get_spectra(id: str, monitor: str) -> Spectra:
        return _pending("GET /api/results/{id}/spectra/{monitor}")  # type: ignore[return-value]

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


def _pending(endpoint: str) -> JSONResponse:
    """Placeholder while U1 is being built: the contract is registered, the body is not."""
    return not_implemented(endpoint, "U1")
