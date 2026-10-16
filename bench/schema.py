"""The result file both sides write: bench/<solver>/out/<tier>/<device>.json (plan §9).

One file per solver, tier and device. Its ``runs`` list holds one run for Meep and one
per backend (cuda, numpy) for etalon. S-parameters are stored as [re, im] pairs per
wavelength under keys "S<out><in>" (point2d: "T21", the probe transfer ratio).
"""

import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from bench.config import BenchConfig, Tier
from bench.devices import Layout, mode_plane

SCHEMA: Literal["etalon-bench/1"] = "etalon-bench/1"

BENCH = Path(__file__).parent

MEEP_CODE_FILES = (
    "__init__.py",
    "config.py",
    "devices.py",
    "schema.py",
    "meep/__init__.py",
    "meep/run_device.py",
)
"""Files whose content defines a Meep result, besides config.yaml (bench/-relative)."""

_KEY = re.compile(r"^[ST](\d)(\d)$")

Complex = tuple[float, float]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class PortRecord(Model):
    name: str
    label: str
    center_um: tuple[float, float, float]
    size_um: tuple[float, float, float]
    normal: Literal["+x", "-x", "+y", "-y", "none"]
    """Outward normal; "none" for point2d's probes."""
    mode: int = 0


class GridRecord(Model):
    dl_um: float
    cells: tuple[int, ...]
    """Cells per axis, PML included."""
    cells_total: int
    pml_um: float
    courant_meep: float
    courant_fraction: float
    """etalon's courant (fraction of the Courant limit) for the same Δt."""
    dt_s: float
    steps: int


class RunRecord(Model):
    backend: Literal["meep-mpi", "cuda", "numpy"]
    status: Literal["ok", "unsupported", "failed", "skipped"]
    message: str | None = None
    needs: str | None = None
    """Milestone that adds what an unsupported run lacks, e.g. "M1"."""
    versions: dict[str, str] = {}
    hardware: dict[str, str | int | None] = {}
    precision: Literal["single", "double"] | None = None
    resolution: int
    grid: GridRecord | None = None
    run_time_s: float
    wall_time_s: float | None = None
    """Setup + time stepping + mode solves and overlaps; imports and process start excluded."""
    stepping_time_s: float | None = None
    extrapolated: bool = False
    """True when wall_time_s is extrapolated from a partial run (then there is no ``s``)."""
    final_decay: float | None = None
    """Largest late |field|² at the output ports (last 10 % of the run) / their largest peak."""
    s: dict[str, list[Complex]] = {}
    n_eff: dict[str, list[float]] = {}
    extra: dict[str, Any] = {}

    @model_validator(mode="after")
    def _consistent(self) -> "RunRecord":
        if self.status == "ok" and not (self.s or self.extrapolated):
            raise ValueError("a run with status 'ok' must carry S-parameters")
        if self.status == "ok" and self.wall_time_s is None:
            raise ValueError("a run with status 'ok' must carry wall_time_s")
        if self.status != "ok" and not self.message:
            raise ValueError(f"a run with status {self.status!r} must say why (message)")
        return self


class DeviceResult(Model):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_: Literal["etalon-bench/1"] = Field(SCHEMA, alias="schema")
    device: str
    tier: str
    solver: Literal["meep", "etalon"]
    config_sha256: str
    """Hash of the resolved device spec (bench.config.BenchConfig.config_sha256)."""
    code_sha256: str
    """Hash of this side's bench code; for Meep, of MEEP_CODE_FILES."""
    git_sha: str
    date: str
    wavelengths_um: list[float] = Field(min_length=1)
    ports: list[PortRecord]
    runs: list[RunRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def _shapes(self) -> "DeviceResult":
        names = {p.name for p in self.ports}
        n = len(self.wavelengths_um)
        for run in self.runs:
            for key, values in run.s.items():
                match = _KEY.match(key)
                if not match or not set(match.groups()) <= names:
                    raise ValueError(
                        f"S key {key!r} does not name two of the ports {sorted(names)}"
                    )
                if len(values) != n:
                    raise ValueError(f"{key} has {len(values)} values for {n} wavelengths")
            for port, indices in run.n_eff.items():
                if port not in names or len(indices) != n:
                    raise ValueError(f"n_eff[{port!r}] must name a port and have {n} values")
        return self

    def run(self, backend: str) -> RunRecord | None:
        """The run of ``backend``, if any."""
        return next((r for r in self.runs if r.backend == backend), None)


def port_records(cfg: BenchConfig, tier: Tier, lay: Layout) -> list[PortRecord]:
    """The ports of a layout as stored in result files (point2d: its two probes)."""
    if not lay.ports:
        return [
            PortRecord(
                name=str(i),
                label="probe",
                center_um=(x, y, 0.0),
                size_um=(0.0, 0.0, 0.0),
                normal="none",
            )
            for i, (x, y) in enumerate(lay.probes, start=1)
        ]
    records = []
    for port in lay.ports:
        centre, size = mode_plane(port.center, port.normal, cfg.ports, tier)
        records.append(
            PortRecord(
                name=port.name,
                label=port.label,
                center_um=centre,
                size_um=size,
                normal=port.normal,
            )
        )
    return records


def encode_complex(values: Any) -> list[Complex]:
    """Complex array → [[re, im], ...]."""
    return [(float(v.real), float(v.imag)) for v in np.asarray(values, dtype=complex).ravel()]


def decode_complex(pairs: list[Complex]) -> np.ndarray:
    """[[re, im], ...] → complex128 array."""
    array = np.asarray(pairs, dtype=float).reshape(-1, 2)
    return array[:, 0] + 1j * array[:, 1]


def out_path(solver: str, tier: str, device: str, root: Path = BENCH) -> Path:
    """bench/<solver>/out/<tier>/<device>.json."""
    return root / solver / "out" / tier / f"{device}.json"


def write_result(path: Path, result: DeviceResult) -> None:
    """Write ``result`` as JSON with every innermost list on one line (readable diffs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result.model_dump(mode="json", by_alias=True), indent=1)
    text = re.sub(
        r"\[\s+([^\[\]{}]*?)\s+\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text
    )
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_result(path: Path) -> DeviceResult:
    """Read and validate a result file."""
    return DeviceResult.model_validate_json(path.read_text(encoding="utf-8"))


def code_sha256(files: tuple[str, ...] = MEEP_CODE_FILES, root: Path = BENCH) -> str:
    """SHA-256 over the named files (line endings normalised), in order."""
    digest = hashlib.sha256()
    for name in files:
        digest.update(name.encode() + b"\0")
        digest.update((root / name).read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def now_utc() -> str:
    """Current time, ISO 8601 UTC to the second."""
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
