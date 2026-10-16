"""``GET /api/system``: versions, platform and the CUDA devices (docs/plan-u0.md §4.3, D11)."""

import json
import platform
import subprocess
import sys
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from etalon import __version__

PROBE_SCRIPT = Path(__file__).with_name("gpu_probe.py")
PROBE_TIMEOUT_S = 20.0


class Device(BaseModel):
    """A CUDA device as CuPy reports it."""

    index: int
    name: str
    memory_bytes: int
    compute_capability: str


class SystemInfo(BaseModel):
    """What this machine and this install are."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    etalon_version: str
    python_version: str
    platform: str
    cupy_status: Literal["ok", "missing", "error"]
    """"missing": CuPy is not installed (``etalon[gpu]``); "error": CuPy or the driver failed."""
    cupy_detail: str | None
    """The error message when ``cupy_status`` is "error"."""
    devices: list[Device]
    """Empty when there is no usable CUDA device; runs then use the CPU backend."""


class GpuProbe:
    """Runs ``gpu_probe.py`` once in a subprocess, in the background, and keeps the answer."""

    def __init__(
        self, command: list[str] | None = None, timeout_s: float = PROBE_TIMEOUT_S
    ) -> None:
        # -P: do not put etalon/studio/ on the probe's sys.path.
        self._command = command or [sys.executable, "-P", str(PROBE_SCRIPT)]
        self._timeout_s = timeout_s
        self._result: dict[str, object] | None = None
        self._thread = threading.Thread(target=self._run, name="etalon-gpu-probe", daemon=True)
        self._start_lock = threading.Lock()
        self._started = False

    def start(self) -> "GpuProbe":
        """Start probing in the background; calling it again does nothing."""
        with self._start_lock:
            if not self._started:
                self._started = True
                self._thread.start()
        return self

    def _run(self) -> None:
        try:
            done = subprocess.run(
                self._command,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
                check=False,
            )
            lines = done.stdout.strip().splitlines()
            if done.returncode != 0 or not lines:
                tail = (done.stderr.strip().splitlines() or ["no output"])[-1]
                raise RuntimeError(f"GPU probe exited with code {done.returncode}: {tail}")
            result = json.loads(lines[-1])
            if not isinstance(result, dict):
                raise RuntimeError("GPU probe printed something other than a JSON object")
            self._result = result
        except subprocess.TimeoutExpired:
            self._result = _error(f"GPU probe timed out after {self._timeout_s:g} s")
        except Exception as error:  # whatever happens, the answer is "no GPU, and why"
            self._result = _error(str(error))

    def result(self) -> dict[str, object]:
        """The probe's answer; starts the probe if needed and waits for it."""
        self.start()
        self._thread.join()
        assert self._result is not None
        return self._result


def _error(detail: str) -> dict[str, object]:
    return {"cupy_status": "error", "cupy_detail": detail, "devices": []}


def system_info(probe: GpuProbe) -> SystemInfo:
    base = {
        "etalon_version": __version__,
        "python_version": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
    }
    found = probe.result()
    gpu = {key: found.get(key) for key in ("cupy_status", "cupy_detail", "devices")}
    try:
        return SystemInfo.model_validate({**base, **gpu})
    except ValidationError as error:
        detail = f"GPU probe output not understood ({error.error_count()} errors)"
        return SystemInfo.model_validate({**base, **_error(detail)})
