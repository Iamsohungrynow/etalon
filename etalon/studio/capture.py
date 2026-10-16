"""Spec capture: what a script builds, from a child process (plan-u1 §2).

The child runs ``python -P -m etalon.studio.runner spec`` with the workspace as
its working directory; see ``runner.py``. Successful captures are cached by the
script's sha256, so an unchanged script costs nothing. Failures are not cached:
the fix may be outside the script (a missing data file), and Retry should retry.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etalon.studio.contract import ScriptError
from etalon.studio.errors import ModelError

TIMEOUT_S = 60.0
TAIL_LINES = 40
TAIL_CHARS = 8000


@dataclass(frozen=True)
class Captured:
    """A captured simulation: the JSON of ``Simulation.model_dump`` and what the script printed."""

    sha256: str
    spec: dict[str, Any]
    stdout_tail: str


def tail(text: str, lines: int = TAIL_LINES, chars: int = TAIL_CHARS) -> str:
    """The last ``lines`` lines of ``text``, at most ``chars`` characters."""
    kept = "\n".join(text.rstrip("\n").splitlines()[-lines:])
    return kept[-chars:]


def child_environment() -> dict[str, str]:
    """The server's environment, plus a non-interactive matplotlib and UTF-8 output."""
    env = dict(os.environ)
    env.update({"MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    return env


def run_child(
    args: list[str], cwd: Path, timeout_s: float
) -> tuple[dict[str, Any] | None, str, bool]:
    """Run ``python -P -m etalon.studio.runner <args[0]> OUT <args[1:]>``.

    Returns (the JSON the child wrote or None, its stdout and stderr, timed out).
    """
    with tempfile.TemporaryDirectory(prefix="etalon-studio-") as scratch:
        out = Path(scratch) / "out.json"
        command = [sys.executable, "-P", "-m", "etalon.studio.runner", args[0], str(out), *args[1:]]
        try:
            done = subprocess.run(
                command,
                cwd=cwd,
                env=child_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                check=False,
            )
            output, timed_out = done.stdout, False
        except subprocess.TimeoutExpired as expired:
            output, timed_out = expired.stdout or b"", True
        text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output
        try:
            result = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result = None
        return result, text, timed_out


class SpecCache:
    """Captured specs by script path, valid while the script's sha256 is unchanged."""

    def __init__(self, timeout_s: float = TIMEOUT_S) -> None:
        self.timeout_s = timeout_s
        self._cache: dict[Path, Captured] = {}
        self._locks: dict[Path, threading.Lock] = {}
        self._guard = threading.Lock()
        self.captures = 0
        """How many child processes have run (tests check the cache with it)."""

    def _lock(self, script: Path) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(script, threading.Lock())

    def get(self, script: Path, workspace: Path) -> Captured:
        """The script's simulation; raises ModelError(422, ScriptError) if there is none."""
        script = script.resolve()
        with self._lock(script):
            sha = hashlib.sha256(script.read_bytes()).hexdigest()
            cached = self._cache.get(script)
            if cached is not None and cached.sha256 == sha:
                return cached
            self.captures += 1
            result, output, timed_out = run_child(["spec", str(script)], workspace, self.timeout_s)
            stdout_tail = tail(output)
            if timed_out:
                raise ModelError(
                    422,
                    ScriptError(
                        code="script_timeout",
                        message="",
                        traceback="",
                        line=None,
                        stdout_tail=stdout_tail,
                    ),
                )
            if result is None:
                # The child died without writing its answer (killed, or the interpreter failed).
                raise ModelError(
                    422,
                    ScriptError(
                        code="script_error",
                        message="",
                        traceback=stdout_tail,
                        line=None,
                        stdout_tail=stdout_tail,
                    ),
                )
            if not result["ok"]:
                raise ModelError(
                    422,
                    ScriptError(
                        code=result["code"],
                        message=result["message"],
                        traceback=result["traceback"],
                        line=result["line"],
                        stdout_tail=stdout_tail,
                    ),
                )
            captured = Captured(sha256=sha, spec=result["spec"], stdout_tail=stdout_tail)
            self._cache[script] = captured
            return captured
