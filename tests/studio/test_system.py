"""S10: the GPU probe and GET /api/system."""

import ast
import json
import sys

import pytest

from etalon.studio import gpu_probe
from etalon.studio.system import PROBE_SCRIPT, GpuProbe, system_info
from tests.studio.conftest import ONE_GPU, FakeProbe, make_client, make_state


def _printing(text: str) -> list[str]:
    return [sys.executable, "-c", f"print({text!r})"]


def test_probe_output_is_parsed():
    probe = GpuProbe(command=_printing(json.dumps(ONE_GPU))).start()
    info = system_info(probe)
    assert info.cupy_status == "ok"
    assert [d.name for d in info.devices] == ["NVIDIA GeForce RTX 4060 Ti"]
    assert info.devices[0].memory_bytes == 8585216000


@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        (_printing("not json"), "Expecting value"),
        (_printing("[1, 2]"), "JSON object"),
        ([sys.executable, "-c", "import sys; sys.exit(3)"], "code 3"),
        ([sys.executable, "-c", "import time; time.sleep(30)"], "timed out"),
        (["no-such-program-etalon"], ""),
    ],
)
def test_probe_failures_become_an_error_status(command, fragment):
    info = system_info(GpuProbe(command=command, timeout_s=2.0))
    assert info.cupy_status == "error"
    assert info.devices == []
    assert fragment in (info.cupy_detail or "")


def test_malformed_device_list_is_an_error():
    info = system_info(FakeProbe({"cupy_status": "ok", "devices": [{"index": "zero"}]}))
    assert (info.cupy_status, info.devices) == ("error", [])
    assert "not understood" in (info.cupy_detail or "")


def test_no_cupy_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "cupy", None)  # makes `import cupy` raise ImportError
    assert gpu_probe.probe() == {"cupy_status": "missing", "cupy_detail": None, "devices": []}


def test_probe_script_imports_nothing_from_etalon():
    tree = ast.parse(PROBE_SCRIPT.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"json", "warnings", "cupy"}


def test_real_probe_answers_in_its_own_format():
    """Runs the real script: with or without CuPy and a GPU, it prints one JSON object."""
    info = system_info(GpuProbe(timeout_s=60.0))
    assert info.cupy_status in ("ok", "missing", "error")
    if info.cupy_status == "ok":
        assert all(d.memory_bytes > 0 for d in info.devices)


def test_system_endpoint(workspace, config_dir):
    body = make_client(make_state(workspace, config_dir)).get("/api/system").json()
    assert body["etalon_version"]
    assert body["python_version"].count(".") == 2
    assert body["cupy_status"] == "ok" and len(body["devices"]) == 1
