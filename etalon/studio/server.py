"""Studio's FastAPI app: the endpoints of ui-ux-spec §9, and the SPA.

U0's routes (workspace, settings, system) are here; U1's (templates, spec,
jobs, results; contract in docs/plan-u1.md §13) are in ``routes.py``.

Nothing here talks to the network beyond answering 127.0.0.1 (see
``security.py``). FastAPI's Swagger/ReDoc pages are off because they load from a
CDN, and its native OpenTelemetry is off so no environment variable can turn on
an exporter.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from etalon import __version__
from etalon.studio.capture import SpecCache
from etalon.studio.contract import EXTRA_SCHEMA_MODELS
from etalon.studio.errors import ApiError, ModelError, StudioError
from etalon.studio.jobs import Job, JobManager
from etalon.studio.routes import register_routes
from etalon.studio.security import HTML_SECURITY_HEADERS, GuardMiddleware
from etalon.studio.settings import SettingsStore, StudioSettings
from etalon.studio.system import GpuProbe, SystemInfo, system_info
from etalon.studio.throughput import ThroughputStore
from etalon.studio.workspace import Workspace, scan

STATIC_DIR = Path(__file__).with_name("static")
INDEX_HTML_TAG = '<html lang="en" data-theme="dark">'
"""The root tag of studio/index.html; the server fills in the saved language and theme."""

# Explicit types: on Windows, Python's mimetypes reads the registry, which can map
# .js to text/plain, and browsers refuse to run module scripts served that way.
MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
}
TELEMETRY_OFF: Any = {"tracing": False, "metrics": False, "logs": False, "auto_configure": False}

NOT_BUILT_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>etalon Studio</title></head>
<body style="font-family: system-ui, sans-serif; margin: 3rem; max-width: 44rem">
<h1>etalon Studio: the web interface is not built</h1>
<p>In the etalon source folder, run <code>pnpm --dir studio install</code> and
<code>pnpm --dir studio build</code>, then reload this page.</p>
<p lang="zh-CN">Studio 网页界面尚未构建。请在 etalon 源代码目录中运行
<code>pnpm --dir studio install</code> 和 <code>pnpm --dir studio build</code>，然后刷新本页。</p>
</body></html>
"""


@dataclass
class StudioState:
    """Everything one running Studio server holds."""

    settings: SettingsStore
    probe: GpuProbe
    token: str
    port: int
    static_dir: Path = field(default=STATIC_DIR)
    config_dir: Path | None = None
    """Where measured throughput is kept for estimates; None keeps it in memory."""
    specs: SpecCache = field(init=False)
    throughput: ThroughputStore = field(init=False)
    jobs: JobManager = field(init=False)

    def __post_init__(self) -> None:
        self.specs = SpecCache()
        self.throughput = ThroughputStore(self.config_dir)
        self.jobs = JobManager(on_finished=self._record_throughput)

    def _record_throughput(self, job: Job) -> None:
        """A run that stepped for a second or more tells the estimate this machine's speed."""
        if job.done is None or job.done["status"] == "failed" or not job.progress:
            return
        last = job.progress[-1]
        if job.started is not None and last["elapsed_s"] >= 1.0:
            self.throughput.record(
                "measured", job.started["backend"], job.started["device"], last["cells_per_s"]
            )


def resolve_language(language: str, accept_language: str) -> str:
    """The UI language for a "system" setting, from the browser's Accept-Language."""
    if language != "system":
        return language
    first = accept_language.split(",")[0].strip().lower()
    return "zh-CN" if first.startswith("zh") else "en"


def _validation_error(code: str, message: str, value: str) -> RequestValidationError:
    return RequestValidationError(
        [{"type": code, "loc": ("body", "workspace"), "msg": message, "input": value}]
    )


def _checked_workspace(value: str) -> Path:
    folder = Path(value).expanduser()
    if not folder.is_absolute():
        raise _validation_error(
            "workspace_not_absolute", "the workspace folder must be an absolute path", value
        )
    if not folder.exists():
        raise _validation_error("workspace_not_found", "this folder does not exist", value)
    if not folder.is_dir():
        raise _validation_error("workspace_not_a_directory", "this is not a folder", value)
    return folder.resolve()


def create_app(state: StudioState) -> FastAPI:
    app = FastAPI(
        title="etalon Studio",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        telemetry=TELEMETRY_OFF,
    )
    app.add_middleware(GuardMiddleware, token=state.token, port=state.port)

    @app.exception_handler(StudioError)
    async def studio_error(request: Request, error: StudioError) -> JSONResponse:
        body = ApiError(code=error.code, message=error.message)
        return JSONResponse(body.model_dump(), status_code=error.status)

    @app.exception_handler(ModelError)
    async def model_error(request: Request, error: ModelError) -> JSONResponse:
        return JSONResponse(error.body.model_dump(mode="json"), status_code=error.status)

    @app.get(
        "/api/workspace",
        operation_id="getWorkspace",
        responses={404: {"model": ApiError, "description": "workspace folder not found"}},
    )
    def get_workspace() -> Workspace:
        folder = Path(state.settings.get().workspace)
        try:
            return scan(folder, jobs=state.jobs.running())
        except FileNotFoundError:
            raise StudioError(
                404, "workspace_missing", f"workspace folder not found: {folder}"
            ) from None

    @app.get("/api/settings", operation_id="getSettings")
    def get_settings() -> StudioSettings:
        return state.settings.get()

    @app.put("/api/settings", operation_id="putSettings")
    def put_settings(settings: StudioSettings) -> StudioSettings:
        folder = _checked_workspace(settings.workspace)
        return state.settings.put(settings.model_copy(update={"workspace": str(folder)}))

    @app.get("/api/system", operation_id="getSystem")
    def get_system() -> SystemInfo:
        return system_info(state.probe)

    register_routes(app, state)

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request) -> Response:
        if path == "api" or path.startswith("api/"):
            raise StudioError(404, "not_found", f"no API endpoint /{path}")
        root = state.static_dir.resolve()
        index = root / "index.html"
        if not index.is_file():
            return HTMLResponse(NOT_BUILT_PAGE, status_code=503, headers=HTML_SECURITY_HEADERS)
        if path:
            candidate = (root / path).resolve()
            if candidate.is_file() and candidate.is_relative_to(root) and candidate != index:
                return _static_file(candidate, immutable=path.startswith("assets/"))
            if path.startswith("assets/"):
                raise StudioError(404, "not_found", f"no file /{path}")
        return _index(index, request)

    def _index(index: Path, request: Request) -> HTMLResponse:
        settings = state.settings.get()
        language = resolve_language(settings.language, request.headers.get("accept-language", ""))
        root_tag = f'<html lang="{language}" data-theme="{settings.theme}">'
        html = index.read_text(encoding="utf-8").replace(INDEX_HTML_TAG, root_tag, 1)
        return HTMLResponse(html, headers={**HTML_SECURITY_HEADERS, "Cache-Control": "no-cache"})

    _add_extra_schemas(app, EXTRA_SCHEMA_MODELS)
    return app


def _add_extra_schemas(app: FastAPI, models: tuple[type[BaseModel], ...]) -> None:
    """Put models that are no route's body (WebSocket messages, binary headers) in the schema."""
    base_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = base_openapi()
            _, top = models_json_schema(
                [(model, "serialization") for model in models],
                ref_template="#/components/schemas/{model}",
            )
            components = schema.setdefault("components", {}).setdefault("schemas", {})
            for name, definition in top.get("$defs", {}).items():
                components.setdefault(name, definition)
        return app.openapi_schema or base_openapi()

    app.openapi = openapi  # type: ignore[method-assign]


def _static_file(path: Path, immutable: bool) -> FileResponse:
    cache = "public, max-age=31536000, immutable" if immutable else "no-cache"
    media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": cache})
