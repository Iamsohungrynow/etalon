"""Reading a run folder: ``.etalon/<script>/runs/<UTC stamp>/`` (plan-u1 §3, §13.4).

``meta.json`` holds the run's metadata and its Simulation's JSON; ``result.npz``
every monitor component as complex data shaped (n_x, n_y, n_wavelengths) with
its node coordinates (keys in ``runner.monitor_layout``).
"""

import hashlib
import json
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from etalon.core.simulation import Simulation
from etalon.studio.binary import finite_range, node_extent, pack
from etalon.studio.contract import (
    ComplexSeries,
    FieldHeader,
    Quantity,
    ResultGrid,
    ResultMeta,
    ResultMonitor,
    Spectra,
)
from etalon.studio.errors import StudioError
from etalon.studio.preview import build_preview, solver_grid
from etalon.studio.workspace import sidecar_dir

RESULT_ID = re.compile(r"^(?P<sim>[0-9a-f]{12})~(?P<stamp>[0-9]{8}T[0-9]{6}Z(-[0-9]+)?)$")
DFT_UNITS = {"E": "V·s/m", "H": "A·s/m"}
"""Units of the DFT of E and H: the field's unit times seconds (F(f) = Σ F(tₙ) e^{iωtₙ} Δt)."""


def parse_result_id(result_id: str) -> tuple[str, str]:
    """(simulation id, stamp); 404 for anything else, so no path can be smuggled in."""
    match = RESULT_ID.match(result_id)
    if match is None:
        raise StudioError(404, "result_not_found", f"no result {result_id!r}")
    return match["sim"], match["stamp"]


def run_dir(script: Path, stamp: str) -> Path:
    return sidecar_dir(script) / "runs" / stamp


def read_meta(folder: Path) -> dict[str, Any] | None:
    try:
        meta: dict[str, Any] = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta


def result_meta(script: Path, meta: dict[str, Any]) -> ResultMeta:
    """``GET /api/results/{id}`` from a finished run's meta.json."""
    sim = Simulation.model_validate(meta["spec"])
    try:
        current = hashlib.sha256(script.read_bytes()).hexdigest()
    except OSError:
        current = None
    return ResultMeta(
        result_id=meta["result_id"],
        simulation_id=meta["simulation_id"],
        status=meta["status"],
        started_at=meta["started_at"],
        finished_at=meta["finished_at"],
        etalon_version=meta["etalon_version"],
        backend=meta["backend"],
        device=meta["device"],
        precision=meta["precision"],
        grid=ResultGrid(**meta["grid"]),
        steps=meta["steps"],
        dt_s=meta["dt_s"],
        wall_time_s=meta["wall_time_s"],
        cells_per_s=meta["cells_per_s"],
        script_sha256=meta["script_sha256"],
        stale=current != meta["script_sha256"],
        preview=build_preview(sim, solver_grid(sim)),
        monitors=[
            ResultMonitor(
                name=monitor["name"],
                geometry=monitor["geometry"],
                components=monitor["components"],
                wavelengths_um=monitor["wavelengths_um"],
                shape=monitor["shape"],
                extent=monitor["extent"],
            )
            for monitor in meta["monitors"]
        ],
    )


class ArrayCache:
    """The last few arrays read from result files (a field viewer asks for the same one often)."""

    def __init__(self, size: int = 6) -> None:
        self._size = size
        self._items: OrderedDict[tuple[str, float, str], NDArray[Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, path: Path, key: str) -> NDArray[Any]:
        cache_key = (str(path), path.stat().st_mtime, key)
        with self._lock:
            if cache_key in self._items:
                self._items.move_to_end(cache_key)
                return self._items[cache_key]
        with np.load(path) as npz:
            array = np.asarray(npz[key])
        with self._lock:
            self._items[cache_key] = array
            while len(self._items) > self._size:
                self._items.popitem(last=False)
        return array


def _monitor(meta: dict[str, Any], name: str) -> dict[str, Any]:
    for monitor in meta["monitors"]:
        if monitor["name"] == name:
            found: dict[str, Any] = monitor
            return found
    raise StudioError(404, "monitor_not_found", f"no monitor {name!r} in this result")


def field_slice(
    folder: Path,
    meta: dict[str, Any],
    cache: ArrayCache,
    monitor_name: str,
    component: str | None,
    quantity: Quantity,
    wavelength_index: int,
) -> bytes:
    """One quantity of one component at one wavelength, as a §13.1 binary ``field``."""
    monitor = _monitor(meta, monitor_name)
    if monitor["geometry"] == "point":
        raise StudioError(409, "point_monitor", f"{monitor_name!r} is a point monitor")
    component = component or monitor["components"][0]
    if component not in monitor["components"]:
        raise StudioError(404, "component_not_found", f"{monitor_name!r} has no {component}")
    wavelengths = monitor["wavelengths_um"]
    if not 0 <= wavelength_index < len(wavelengths):
        raise StudioError(404, "wavelength_not_found", f"no wavelength {wavelength_index}")
    path = folder / "result.npz"
    key = f"m{monitor['index']}.{component}"
    data = cache.get(path, key)[:, :, wavelength_index]
    x = cache.get(path, f"{key}.x")
    y = cache.get(path, f"{key}.y")
    values: NDArray[Any]
    if quantity == "abs":
        values = np.abs(data)
    elif quantity == "real":
        values = data.real
    elif quantity == "imag":
        values = data.imag
    else:
        values = np.angle(data)
    values = np.asarray(values, dtype=np.float32)
    low, high = finite_range(values)
    header = FieldHeader(
        shape=(int(values.shape[0]), int(values.shape[1])),
        extent=node_extent(x, y),
        min=low,
        max=high,
        component=component,
        unit="rad" if quantity == "phase" else DFT_UNITS[component[0]],
        quantity=quantity,
        wavelength_um=float(wavelengths[wavelength_index]),
    )
    return pack(header, values)


def spectra(folder: Path, meta: dict[str, Any], cache: ArrayCache, monitor_name: str) -> Spectra:
    """A point monitor's complex spectrum of every recorded component."""
    monitor = _monitor(meta, monitor_name)
    if monitor["geometry"] != "point":
        raise StudioError(409, "not_point_monitor", f"{monitor_name!r} is not a point monitor")
    path = folder / "result.npz"
    components = {}
    for component in monitor["components"]:
        data = cache.get(path, f"m{monitor['index']}.{component}")[0, 0, :]
        components[component] = ComplexSeries(
            re=[float(v) for v in data.real], im=[float(v) for v in data.imag]
        )
    return Spectra(
        monitor=monitor_name, wavelengths_um=monitor["wavelengths_um"], components=components
    )
