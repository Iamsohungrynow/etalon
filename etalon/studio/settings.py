"""Studio settings: the model, where they live on disk, and how they are saved.

Every field except ``workspace`` is saved to ``<config dir>/studio.json``. The
workspace comes from ``etalon studio [FOLDER]`` and can be switched while Studio
runs, but is not remembered (docs/plan-u0.md §8, D6).
"""

import json
import os
import sys
import threading
import warnings
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SETTINGS_FILE = "studio.json"


class StudioSettings(BaseModel):
    """What the Settings screen edits (ui-ux-spec §5.7)."""

    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)

    backend: str = Field("auto", pattern=r"^(auto|cpu|cuda:\d+)$")
    """Backend for runs: "auto" (a CUDA device if there is one, else the CPU), "cpu" or "cuda:N"."""
    language: Literal["system", "en", "zh-CN"] = "system"
    """UI language; "system" follows the browser."""
    theme: Literal["dark", "light", "system"] = "dark"
    """Colour theme; "system" follows the OS."""
    units: Literal["um", "nm"] = "um"
    """Length unit for display."""
    live_snapshots: bool = False
    """Show a live low-resolution field while a simulation runs."""
    workspace: str
    """Absolute path of the folder whose scripts Studio lists."""


def config_dir() -> Path:
    """Per-user config directory; ``ETALON_CONFIG_DIR`` overrides it."""
    override = os.environ.get("ETALON_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "etalon"


def write_atomically(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` through a temporary file, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


class SettingsStore:
    """The current settings, shared by request threads; saves on every change.

    ``directory=None`` keeps everything in memory (used to build the OpenAPI schema).
    """

    def __init__(self, directory: Path | None, workspace: Path) -> None:
        self._directory = directory
        self._lock = threading.Lock()
        self._settings = self._load(workspace)

    def _load(self, workspace: Path) -> StudioSettings:
        saved: dict[str, object] = {}
        path = None if self._directory is None else self._directory / SETTINGS_FILE
        if path is not None and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("not a JSON object")
                fields = set(StudioSettings.model_fields) - {"workspace"}
                saved = {key: value for key, value in raw.items() if key in fields}
                return StudioSettings.model_validate({**saved, "workspace": str(workspace)})
            except (OSError, ValueError, ValidationError) as error:
                warnings.warn(
                    f"ignoring unreadable Studio settings {path} ({error}); using defaults",
                    stacklevel=2,
                )
        return StudioSettings(workspace=str(workspace))

    def get(self) -> StudioSettings:
        with self._lock:
            return self._settings

    def put(self, settings: StudioSettings) -> StudioSettings:
        with self._lock:
            self._settings = settings
            if self._directory is not None:
                saved = settings.model_dump(exclude={"workspace"})
                text = json.dumps(saved, indent=2, sort_keys=True) + "\n"
                write_atomically(self._directory / SETTINGS_FILE, text)
            return settings
