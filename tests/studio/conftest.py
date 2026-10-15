"""Shared helpers for the Studio server tests (docs/plan-u0.md §6, S1–S14)."""

import hashlib
import json
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from etalon.studio.security import TOKEN_HEADER
from etalon.studio.server import StudioState, create_app
from etalon.studio.settings import SettingsStore
from etalon.studio.system import GpuProbe

TOKEN = "test-token"
PORT = 8787
BASE_URL = f"http://127.0.0.1:{PORT}"

ONE_GPU = {
    "cupy_status": "ok",
    "cupy_detail": None,
    "devices": [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 4060 Ti",
            "memory_bytes": 8585216000,
            "compute_capability": "8.9",
        }
    ],
}


class FakeProbe(GpuProbe):
    """A GPU probe with a fixed answer that never starts a subprocess."""

    def __init__(self, answer: dict[str, object] | None = None) -> None:
        super().__init__(command=["unused"])
        self.answer = ONE_GPU if answer is None else answer

    def start(self) -> "FakeProbe":
        return self

    def result(self) -> dict[str, object]:
        return self.answer


def write_script(folder: Path, relative: str, text: str = "import etalon as et\n") -> Path:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def write_status(script: Path, raw: str | dict[str, object]) -> Path:
    """Write ``.etalon/<script name>/status.json`` next to ``script``."""
    path = script.parent / ".etalon" / script.name / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw if isinstance(raw, str) else json.dumps(raw), encoding="utf-8")
    return path


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "config"
    monkeypatch.setenv("ETALON_CONFIG_DIR", str(directory))
    monkeypatch.delenv("ETALON_STUDIO_TOKEN", raising=False)
    return directory


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    folder = tmp_path / "workspace"
    folder.mkdir()
    return folder


def make_state(
    workspace: Path,
    config_dir: Path | None,
    static_dir: Path | None = None,
    probe: GpuProbe | None = None,
) -> StudioState:
    state = StudioState(
        settings=SettingsStore(config_dir, workspace),
        probe=probe or FakeProbe(),
        token=TOKEN,
        port=PORT,
    )
    if static_dir is not None:
        state.static_dir = static_dir
    return state


def make_client(state: StudioState, token: str | None = TOKEN) -> TestClient:
    client = TestClient(create_app(state), base_url=BASE_URL)
    if token is not None:
        client.headers[TOKEN_HEADER] = token
    return client


@pytest.fixture
def client(workspace: Path, config_dir: Path) -> TestClient:
    return make_client(make_state(workspace, config_dir))
