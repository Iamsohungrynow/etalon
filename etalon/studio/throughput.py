"""This machine's measured cells per second, for the time estimate (plan-u1 §10.8).

Two sources per backend (``cpu``, ``cuda:N``): the last finished run
("measured") and the last ``POST /api/calibrate`` ("calibration"). The estimate
uses the more recent one. Kept in ``<config dir>/throughput.json``.
"""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ValidationError

from etalon.studio.settings import write_atomically

THROUGHPUT_FILE = "throughput.json"
Basis = Literal["measured", "calibration"]


class Measurement(BaseModel):
    cells_per_s: float
    device: str
    at: AwareDatetime


class BackendThroughput(BaseModel):
    measured: Measurement | None = None
    calibration: Measurement | None = None


class ThroughputStore:
    """Measured throughput by backend; ``directory=None`` keeps it in memory."""

    def __init__(self, directory: Path | None) -> None:
        self._path = None if directory is None else directory / THROUGHPUT_FILE
        self._lock = threading.Lock()
        self._data: dict[str, BackendThroughput] = self._load()

    def _load(self) -> dict[str, BackendThroughput]:
        if self._path is None or not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {key: BackendThroughput.model_validate(value) for key, value in raw.items()}
        except (OSError, ValueError, AttributeError, ValidationError):
            return {}  # a damaged file only loses the estimate

    def record(self, basis: Basis, backend: str, device: str, cells_per_s: float) -> None:
        if not cells_per_s > 0:
            return
        entry = Measurement(cells_per_s=cells_per_s, device=device, at=datetime.now(UTC))
        with self._lock:
            current = self._data.get(backend, BackendThroughput())
            self._data[backend] = current.model_copy(update={basis: entry})
            if self._path is not None:
                raw = {key: value.model_dump(mode="json") for key, value in self._data.items()}
                write_atomically(self._path, json.dumps(raw, indent=2, sort_keys=True) + "\n")

    def lookup(self, backend: str) -> tuple[Basis, float] | None:
        """The more recent of the measured and calibrated throughput of ``backend``."""
        with self._lock:
            entry = self._data.get(backend)
        if entry is None:
            return None
        options: list[tuple[datetime, Basis, float]] = []
        if entry.measured is not None:
            options.append((entry.measured.at, "measured", entry.measured.cells_per_s))
        if entry.calibration is not None:
            options.append((entry.calibration.at, "calibration", entry.calibration.cells_per_s))
        if not options:
            return None
        _, basis, value = max(options)
        return basis, value
