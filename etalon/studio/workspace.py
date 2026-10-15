"""The Workspace list: one row per simulation script (ui-ux-spec §5.1, docs/plan-u0.md §4.3).

A row is one ``.py`` file under the workspace folder. Its status comes from the
sidecar ``<script's folder>/.etalon/<script name>/status.json``, which Studio's
job runner writes from U2; no sidecar means a draft. The scan never fails
because of one bad file: an unreadable sidecar gives the status "unknown".
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

MAX_SCRIPTS = 5000
SIDECAR_DIR = ".etalon"
STATUS_FILE = "status.json"
SKIP_DIR_NAMES = frozenset({"node_modules", "site-packages"})

Status = Literal["draft", "running", "done", "failed", "cancelled", "unknown"]
StatusReason = Literal["unreadable", "invalid_json", "invalid_fields"]


class SidecarStatus(BaseModel):
    """``status.json``, written by Studio's job runner (U2) after each change of a run."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["running", "done", "failed", "cancelled"]
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    backend: str | None = None
    device: str | None = None
    cells: int | None = None
    wall_time_s: float | None = None
    step: int | None = None
    total_steps: int | None = None
    eta_s: float | None = None
    script_sha256: str | None = None


class SimulationRow(BaseModel):
    """One simulation script and the state of its last run."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    id: str
    """12 hex characters of sha256(relative POSIX path): stable while the file is not moved."""
    name: str
    """File name, e.g. ``ring_r10_g200.py``."""
    path: str
    """Path relative to the workspace folder, with ``/`` separators."""
    status: Status
    status_reason: StatusReason | None = None
    """Why the status is "unknown"."""
    last_run: AwareDatetime | None = None
    """When the last run finished (or started, while it runs)."""
    backend: str | None = None
    """``cuda:0``, ``cpu``, ..."""
    device: str | None = None
    """GPU or CPU model the run used."""
    cells: int | None = None
    wall_time_s: float | None = None
    step: int | None = None
    total_steps: int | None = None
    eta_s: float | None = None
    stale: bool = False
    """The script changed after its last finished run."""
    modified: AwareDatetime
    """Last modification time of the script."""


class Workspace(BaseModel):
    """``GET /api/workspace``."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    folder: str
    """Absolute path of the workspace folder, in the platform's own notation."""
    simulations: list[SimulationRow]
    """Sorted by path, case-insensitively."""
    truncated: bool
    """True when the scan stopped at MAX_SCRIPTS scripts."""


def simulation_id(relative_path: str) -> str:
    """Stable, URL-safe id of the script at ``relative_path`` (POSIX separators)."""
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:12]


def _skip(name: str) -> bool:
    """Hidden and private names: ``.git``, ``.venv``, ``.etalon``, ``__pycache__``, ``_util.py``."""
    return name.startswith((".", "_"))


def find_scripts(folder: Path, limit: int = MAX_SCRIPTS) -> tuple[list[Path], bool]:
    """``.py`` files under ``folder``, in no particular order, and whether ``limit`` was hit."""
    found: list[Path] = []
    pending = [folder]
    while pending:
        directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue  # unreadable folder: list what we can
        if directory != folder and any(e.name == "pyvenv.cfg" for e in entries):
            continue  # a virtual environment
        for entry in entries:
            if _skip(entry.name):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in SKIP_DIR_NAMES:
                        pending.append(Path(entry.path))
                elif entry.name.endswith(".py") and entry.is_file():
                    if len(found) == limit:
                        return found, True
                    found.append(Path(entry.path))
            except OSError:
                continue
    return found, False


def _read_sidecar(script: Path) -> SidecarStatus | StatusReason | None:
    """The script's sidecar status, the reason it cannot be read, or None for a draft."""
    path = script.parent / SIDECAR_DIR / script.name / STATUS_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return "unreadable"
    try:
        raw = json.loads(text)
    except ValueError:
        return "invalid_json"
    try:
        return SidecarStatus.model_validate(raw)
    except ValidationError:
        return "invalid_fields"


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def row_for(script: Path, folder: Path) -> SimulationRow:
    relative = script.relative_to(folder).as_posix()
    modified = datetime.fromtimestamp(script.stat().st_mtime, tz=UTC)
    base = {"id": simulation_id(relative), "name": script.name, "path": relative}
    sidecar = _read_sidecar(script)
    if sidecar is None:
        return SimulationRow(**base, status="draft", modified=modified)
    if isinstance(sidecar, str):
        return SimulationRow(**base, status="unknown", status_reason=sidecar, modified=modified)
    finished = sidecar.status != "running"
    stale = (
        finished and sidecar.script_sha256 is not None and _sha256(script) != sidecar.script_sha256
    )
    return SimulationRow(
        **base,
        status=sidecar.status,
        last_run=(sidecar.finished_at or sidecar.started_at) if finished else sidecar.started_at,
        backend=sidecar.backend,
        device=sidecar.device,
        cells=sidecar.cells,
        wall_time_s=sidecar.wall_time_s,
        step=sidecar.step,
        total_steps=sidecar.total_steps,
        eta_s=sidecar.eta_s,
        stale=stale,
        modified=modified,
    )


def scan(folder: Path, limit: int = MAX_SCRIPTS) -> Workspace:
    """All simulation scripts under ``folder``; raises FileNotFoundError if it is gone."""
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    scripts, truncated = find_scripts(folder, limit)
    rows = []
    for script in scripts:
        try:
            rows.append(row_for(script, folder))
        except OSError:
            continue  # deleted between listing and reading
    rows.sort(key=lambda row: (row.path.casefold(), row.path))
    return Workspace(folder=str(folder), simulations=rows, truncated=truncated)
