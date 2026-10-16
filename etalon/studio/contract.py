"""The U1 API contract as code: every shape of docs/plan-u1.md §13.

These models define the OpenAPI schema, and the frontend's types are generated
from it (``python -m etalon.studio.openapi``, then ``pnpm --dir studio gen:api``),
so a change here is a change of the contract: it goes into plan-u1 §13 first.

The WebSocket messages and the headers of the binary arrays are not the body of
any HTTP route; ``server.py`` adds them to the schema's components so the
frontend gets their types too (``EXTRA_SCHEMA_MODELS``).

Units: lengths in µm, time in s, as in the Python API. The server never sends
prose: warnings and errors carry codes and numbers, and the frontend words them.
"""

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel

from etalon.core.base import FieldComponent

Vec3 = tuple[float, float, float]
"""(x, y, z), µm."""
Extent = tuple[float, float, float, float]
"""[x_first, x_last, y_first, y_last], µm: the first and last nodes along each axis."""
Shape2 = tuple[int, int]
"""[n_x, n_y]: axis 0 is x, axis 1 is y (C order, y varies fastest)."""

TemplateId = Literal["vacuum_pulse", "strip_waveguide", "sharp_bend", "phc_waveguide"]
MonitorGeometry = Literal["point", "line", "plane", "box"]
Quantity = Literal["abs", "real", "imag", "phase"]
RunStatus = Literal["done", "failed", "cancelled"]
Suggestion = Literal["out_of_memory", "nan", "unsupported"]

NAME_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
"""File name of a new simulation script, without ``.py``."""


class Model(BaseModel):
    """Base of the contract models: field docstrings become schema descriptions."""

    model_config = ConfigDict(use_attribute_docstrings=True)


# §13.1 Binary arrays ------------------------------------------------------------------
class ArrayHeaderBase(Model):
    """JSON header of a binary array (§13.1).

    Layout: ``[uint32 LE N][N bytes UTF-8 JSON header][zero padding to a multiple
    of 4][float32 LE data]``; the data starts at ``4 + N`` rounded up to a
    multiple of 4, so the client views it as a Float32Array without copying.
    """

    shape: Shape2
    """[n_x, n_y], the solver's own C order: axis 0 = x, axis 1 = y, y varying fastest."""
    extent: Extent
    """[x_first, x_last, y_first, y_last], µm, of the first and last nodes (uniform spacing)."""
    min: float
    """Smallest finite value in the data (0 when there is none)."""
    max: float
    """Largest finite value in the data (0 when there is none)."""
    component: str
    """Field component on whose nodes the data sits (Ex, Ey, Hz)."""
    unit: str
    """Unit of the values, free text (e.g. "1", "A/m", "V·s/m", "rad")."""


class PermittivityHeader(ArrayHeaderBase):
    """``GET /api/simulations/{id}/permittivity``: the solver's own εr, PML included."""

    kind: Literal["permittivity"] = "permittivity"
    pml_cells: int
    """PML cells on each face; the region starts this many nodes in from each edge."""


class FieldHeader(ArrayHeaderBase):
    """``GET /api/results/{id}/fields/{monitor}``: one quantity of one component at one λ."""

    kind: Literal["field"] = "field"
    quantity: Quantity
    wavelength_um: float


class SnapshotHeader(ArrayHeaderBase):
    """A live Hz snapshot (WebSocket binary frame), downsampled to at most 256 × 256.

    ``extent`` describes the downsampled nodes.
    """

    kind: Literal["snapshot"] = "snapshot"
    step: int
    """Time step the snapshot was taken at."""


class ArrayHeader(RootModel[PermittivityHeader | FieldHeader | SnapshotHeader]):
    """Any binary array header, told apart by ``kind``."""

    root: Annotated[PermittivityHeader | FieldHeader | SnapshotHeader, Field(discriminator="kind")]


# §13.2 Simulations and templates ------------------------------------------------------
class Template(Model):
    """A template ``POST /api/simulations`` can copy; title and description are i18n keys."""

    id: TemplateId
    file: str
    """File name of the template script, e.g. ``phc_waveguide.py``."""


class CreateSimulation(Model):
    """Body of ``POST /api/simulations``."""

    template: TemplateId
    name: str = Field(json_schema_extra={"pattern": NAME_PATTERN})
    """File name without ``.py``: ``[A-Za-z0-9_-]{1,64}``; anything else is 422 ``bad_name``."""


class Region(Model):
    center: Vec3
    size: Vec3
    """size_z = 0 for a 2D simulation; the PML is outside this box."""


class PreviewPml(Model):
    layers: int
    """PML cells on each face."""
    thickness: Vec3
    """[tx, ty, tz], µm, of the PML on each face of each axis (0 along a flat axis)."""


class Background(Model):
    n: float
    name: str | None


class PreviewMedium(Model):
    """A medium used by at least one structure, in order of first use."""

    id: str
    """``medium:<i>``."""
    name: str | None
    n: float


class PreviewStructure(Model):
    id: str
    """``structure:<i>``, i = index in ``Simulation.structures``."""
    name: str | None
    kind: Literal["Box"]
    center: Vec3
    size: Vec3
    medium_id: str
    """Id of its entry in ``media``."""


class PreviewSource(Model):
    id: str
    """``source:<i>``, i = index in ``Simulation.sources``."""
    name: str | None
    kind: Literal["PointSource"]
    center: Vec3
    component: FieldComponent
    wavelength_um: float
    """Centre wavelength of the pulse."""
    bandwidth_um: float
    """Full width of the pulse's wavelength band."""


class PreviewMonitor(Model):
    id: str
    """``monitor:<name>``."""
    name: str
    kind: Literal["DFTMonitor"]
    geometry: MonitorGeometry
    """How many axes have size > 0: 0 point, 1 line, 2 plane, 3 box."""
    center: Vec3
    size: Vec3
    wavelengths_um: list[float]
    components: list[FieldComponent]
    """The components it records (all the simulation computes when the script names none)."""


class PreviewGrid(Model):
    """The Yee grid the solver builds."""

    dx: float
    """Cell size along x, µm."""
    dy: float
    """Cell size along y, µm."""
    nx: int
    """Cells along x, PML included."""
    ny: int
    """Cells along y, PML included."""
    region_cells: Shape2
    """[rx, ry]: cells inside the simulation region, PML excluded."""
    dt_s: float
    courant: float
    steps: int


class Preview(Model):
    """What the Setup screen draws: the simulation's objects, in µm.

    Ids: ``medium:<i>``, ``structure:<i>``, ``source:<i>``, ``monitor:<name>``,
    ``boundary``, ``grid``.
    """

    is_2d: bool
    plane_z: float
    """The simulated plane of a 2D simulation (the region's centre z)."""
    region: Region
    pml: PreviewPml
    background: Background
    media: list[PreviewMedium]
    structures: list[PreviewStructure]
    sources: list[PreviewSource]
    monitors: list[PreviewMonitor]
    grid: PreviewGrid | None
    """Null when this build of the solver cannot grid the simulation (3D, until M1)."""


class Estimate(Model):
    """What a run will cost, before it starts."""

    cells: int
    """Cells, PML included."""
    memory_bytes: int
    """Fields, coefficients, CPML and monitor accumulators on the device."""
    steps: int
    dt_s: float
    run_time_s: float
    """Simulated time, ``Simulation.run_time``."""
    seconds: float | None
    """Estimated wall time; null when ``basis`` is "unknown"."""
    cells_per_s: float | None
    """Cell updates per second the estimate assumes; null when ``basis`` is "unknown"."""
    basis: Literal["measured", "calibration", "unknown"]
    """Where ``cells_per_s`` comes from: earlier runs on this machine, ``POST
    /api/calibrate``, or neither yet."""


class MeshCoarseParams(Model):
    cells_per_wavelength: float
    minimum: float
    medium: str | None
    """Name of the highest-index medium (null when it has none)."""
    wavelength_um: float
    """The shortest wavelength of interest (source band edge or monitor wavelength)."""


class PmlThinParams(Model):
    thickness_um: float
    half_wavelength_um: float
    """Half the longest source wavelength in the background medium."""


class NearPmlParams(Model):
    cells: int
    """Whole cells between the object and the PML (0, 1 or 2)."""


class MemoryLargeParams(Model):
    bytes: int


class UnsupportedParams(Model):
    feature: Literal["3d", "tm"]
    """"3d": size_z > 0; "tm": a 2D TM component (Ez, Hx, Hy) in a source or monitor."""
    milestone: str
    """Solver milestone that adds it, e.g. "M1"."""


class WarningBase(Model):
    severity: Literal["warning", "error"]
    """"error" disables Run; warnings never do."""
    object_id: str | None
    """Preview id of the object the warning is about, if any."""


class MeshCoarseWarning(WarningBase):
    """Fewer than ``minimum`` cells per wavelength in the highest-index medium."""

    code: Literal["mesh_coarse"]
    params: MeshCoarseParams


class PmlThinWarning(WarningBase):
    """The PML is thinner than half a wavelength."""

    code: Literal["pml_thin"]
    params: PmlThinParams


class NearPmlWarning(WarningBase):
    """A source or monitor within 3 cells of the PML."""

    code: Literal["near_pml"]
    params: NearPmlParams


class MemoryLargeWarning(WarningBase):
    """The run needs more than 4 GB."""

    code: Literal["memory_large"]
    params: MemoryLargeParams


class UnsupportedWarning(WarningBase):
    """Something this build of the solver cannot run; always an error."""

    code: Literal["unsupported"]
    params: UnsupportedParams


AnyWarning = (
    MeshCoarseWarning | PmlThinWarning | NearPmlWarning | MemoryLargeWarning | UnsupportedWarning
)


# The contract's name for it; it shadows the builtin only inside this module.
class Warning(RootModel[AnyWarning]):
    """A Setup warning: a code, its numbers, and the object it is about (§13.2)."""

    root: Annotated[AnyWarning, Field(discriminator="code")]


class SimulationSpec(Model):
    """``GET /api/simulations/{id}/spec``: what the script builds, captured at ``run()``."""

    script_sha256: str
    spec: dict[str, Any]
    """``Simulation.model_dump(mode="json")``, free-form."""
    preview: Preview
    estimate: Estimate | None
    """Null when the solver cannot grid the simulation (see ``preview.grid``)."""
    warnings: list[Warning]
    stdout_tail: str
    """The last lines the script printed (stdout and stderr) while it was captured."""


class ScriptError(Model):
    """422 from the spec, permittivity and similar routes: the script did not give a Simulation.

    ``script_error``: it raised (``traceback``, and ``line`` in the script when the
    traceback passes through it); ``script_timeout``: it ran 60 s without reaching
    ``run()``; ``no_simulation``: it finished without calling ``run()`` and
    defines no module-level Simulation.
    """

    code: Literal["script_error", "script_timeout", "no_simulation"]
    message: str
    """The exception's own message (Python's words, not Studio's)."""
    traceback: str
    line: int | None
    """Line in the script where it failed, if the traceback passes through the script."""
    stdout_tail: str


class Calibration(Model):
    """``POST /api/calibrate``: this machine's measured throughput, kept for ``Estimate``."""

    cells_per_s: float
    backend: str
    """``cpu`` or ``cuda:N``."""
    device: str
    """CPU or GPU model."""


# §13.3 Jobs -----------------------------------------------------------------------------
class JobStarted(Model):
    """202 from ``POST /api/simulations/{id}/run``."""

    job_id: str
    result_id: str
    """Id the run's result will have; ``GET /api/results/{id}`` answers once the run has data."""


class AlreadyRunning(Model):
    """409 from ``POST /api/simulations/{id}/run``: one job at a time per simulation."""

    code: Literal["already_running"]
    message: str
    job_id: str
    """The job that is running."""


class Cancelling(Model):
    """202 from ``DELETE /api/jobs/{job_id}``; the final status arrives on the WebSocket."""

    status: Literal["cancelling"]


class StartedMessage(Model):
    """First message on ``WS /api/jobs/{job_id}``, once the solver is built.

    Absent when the script fails before it reaches ``run()``: then ``history``
    and ``done`` follow directly.
    """

    type: Literal["started"]
    total: int
    """Time steps the run will take."""
    grid: Shape2
    """[nx, ny], PML included."""
    dt_s: float
    backend: str
    """``cpu`` or ``cuda:N``."""
    device: str
    snapshots: bool
    """Whether binary snapshot frames will follow."""


class Progress(Model):
    """At most 4 per second while the solver steps."""

    type: Literal["progress"]
    step: int
    total: int
    elapsed_s: float
    """Wall time since stepping began."""
    eta_s: float
    cells_per_s: float
    energy: float
    """Discrete field energy W = ½ΔxΔy Σ(ε0 εr E² + μ0 H²), absolute, J/m in 2D."""


class LogLine(Model):
    type: Literal["log"]
    stream: Literal["stdout", "stderr", "etalon"]
    """What the script printed, or Studio's own runner lines ("etalon")."""
    line: str


class HistoryMessage(Model):
    """Second message on connect: everything so far."""

    type: Literal["history"]
    progress: list[Progress]
    """Every progress point so far."""
    log: list[LogLine]
    """The last 500 log lines."""


class JobError(Model):
    message: str
    traceback: str
    line: int | None
    """Line in the script where it failed, if the traceback passes through the script."""


class DoneMessage(Model):
    """Last message; the server closes the socket after it."""

    type: Literal["done"]
    status: RunStatus
    result_id: str | None
    """Null when the run left no monitor data (it failed before or while building the solver)."""
    error: JobError | None
    suggestion: Suggestion | None
    """A recognised failure: out of memory, NaN fields, or a feature this build lacks."""


AnyJobMessage = StartedMessage | HistoryMessage | Progress | LogLine | DoneMessage


class JobMessage(RootModel[AnyJobMessage]):
    """A JSON text frame on ``WS /api/jobs/{job_id}``, told apart by ``type``.

    The socket opens with subprotocols ``["etalon.v1", "token.<token>"]`` and the
    server accepts ``etalon.v1``. Binary frames are snapshots (§13.1, ``kind:
    "snapshot"``).
    """

    root: Annotated[AnyJobMessage, Field(discriminator="type")]


# §13.4 Results ----------------------------------------------------------------------------
class ResultGrid(Model):
    nx: int
    ny: int
    dx: float
    dy: float


class ResultMonitor(Model):
    name: str
    geometry: MonitorGeometry
    components: list[FieldComponent]
    wavelengths_um: list[float]
    shape: Shape2 | None
    """[n_x, n_y] of the first listed component's nodes (each component's own shape is in
    its field header); null for a point monitor."""
    extent: Extent | None
    """Extent of the first listed component's nodes, µm; null for a point monitor."""


class ResultMeta(Model):
    """``GET /api/results/{id}``; the id is ``<simulation id>~<UTC stamp>``."""

    result_id: str
    simulation_id: str
    title: str
    """The script's title now (its docstring's first line, as in the workspace row)."""
    status: RunStatus
    """"failed" here means the script failed after ``run()`` returned, so the data exists."""
    started_at: AwareDatetime
    finished_at: AwareDatetime
    etalon_version: str
    backend: str
    """``cpu`` or ``cuda:N``."""
    device: str
    precision: Literal["single", "double"]
    grid: ResultGrid
    steps: int
    """Time steps actually taken (fewer than planned when cancelled)."""
    dt_s: float
    wall_time_s: float
    cells_per_s: float
    script_sha256: str
    stale: bool
    """The script changed after this run."""
    preview: Preview
    """The Preview at run time, for outline overlays."""
    monitors: list[ResultMonitor]


class ComplexSeries(Model):
    re: list[float]
    im: list[float]


class Spectra(Model):
    """``GET /api/results/{id}/spectra/{monitor}``: a point monitor's complex spectrum."""

    monitor: str
    wavelengths_um: list[float]
    components: dict[str, ComplexSeries]
    """Keyed by component (Ex, Ey, Hz); time convention exp(−iωt)."""


# §13.5 Still 501 ----------------------------------------------------------------------------
class NotImplementedBody(Model):
    """501 from an endpoint of ui-ux-spec §9 that a later milestone adds."""

    code: Literal["not_implemented"]
    endpoint: str
    """The endpoint, e.g. ``GET /api/results/{id}/s-matrix``."""
    arrives_in: str
    """The milestone that adds it, e.g. "M2"."""


EXTRA_SCHEMA_MODELS: tuple[type[BaseModel], ...] = (ArrayHeader, JobMessage)
"""Models that are no route's body but whose types the frontend needs."""
