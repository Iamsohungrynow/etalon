"""S1, S12, S14: the `etalon studio` command, binding, and import weight."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from etalon import cli
from etalon.studio import launch
from tests.studio.conftest import FakeProbe, free_port

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def quiet_launch(monkeypatch):
    """`etalon studio` in-process, without serving, probing or opening anything."""
    opened: list[str] = []
    monkeypatch.setattr(launch, "GpuProbe", FakeProbe)
    monkeypatch.setattr(launch.uvicorn.Server, "run", lambda self, sockets=None: None)
    monkeypatch.setattr(launch.webbrowser, "open", opened.append)
    return opened


# S12 ---------------------------------------------------------------------------------
def test_help_lists_studio(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    assert "studio" in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert cli.main([]) == 0
    assert "studio" in capsys.readouterr().out


def test_missing_folder_exits_2(tmp_path, config_dir, capsys, quiet_launch):
    assert cli.main(["studio", str(tmp_path / "gone"), "--no-browser"]) == 2
    assert "folder not found" in capsys.readouterr().err


def test_busy_port_exits_2(workspace, config_dir, capsys, quiet_launch):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        assert cli.main(["studio", str(workspace), "--port", str(port), "--no-browser"]) == 2
    assert f"port {port} is in use" in capsys.readouterr().err


def test_prints_the_link_and_opens_no_browser(workspace, config_dir, capsys, quiet_launch):
    port = free_port()
    assert cli.main(["studio", str(workspace), "--port", str(port), "--no-browser"]) == 0
    out = capsys.readouterr().out
    assert f"http://127.0.0.1:{port}/?token=" in out
    assert str(workspace) in out
    assert quiet_launch == []


def test_opens_the_browser_once_the_server_has_started(workspace, config_dir, monkeypatch):
    opened = threading.Event()
    seen: list[str] = []

    def fake_open_when_ready(server, url):
        seen.append(url)
        opened.set()

    monkeypatch.setattr(launch, "GpuProbe", FakeProbe)
    monkeypatch.setattr(launch.uvicorn.Server, "run", lambda self, sockets=None: None)
    monkeypatch.setattr(launch, "_open_when_ready", fake_open_when_ready)
    port = free_port()
    assert cli.main(["studio", str(workspace), "--port", str(port)]) == 0
    assert opened.wait(5)
    assert seen[0].startswith(f"http://127.0.0.1:{port}/?token=")


def test_bound_socket_is_loopback_only():
    sock = launch.bind_socket(0)
    try:
        assert sock.getsockname()[0] == "127.0.0.1"
    finally:
        sock.close()


# S1 ----------------------------------------------------------------------------------
def test_running_server_answers_on_loopback_only(workspace, tmp_path):
    port = free_port()
    env = {
        **os.environ,
        "ETALON_CONFIG_DIR": str(tmp_path / "config"),
        "ETALON_STUDIO_TOKEN": "s1-token",
    }
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "etalon.cli",
            "studio",
            str(workspace),
            "--port",
            str(port),
            "--no-browser",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _wait_for_port(port, timeout=60), "Studio did not start within 60 s"
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
        for address in _other_local_addresses():
            with pytest.raises(OSError):
                socket.create_connection((address, port), timeout=2).close()
    finally:
        server.terminate()
        output, _ = server.communicate(timeout=30)
    assert f"http://127.0.0.1:{port}/?token=s1-token" in output


def _wait_for_port(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _other_local_addresses() -> list[str]:
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return sorted({str(info[4][0]) for info in infos} - {"127.0.0.1"})


# S14 ---------------------------------------------------------------------------------
def test_studio_server_imports_no_heavy_packages():
    heavy = ("scipy", "xarray", "pandas", "matplotlib", "cupy")
    probe = (
        "import json, sys\nimport etalon.cli, etalon.studio.launch\n"
        f"print(json.dumps(sorted({{m.split('.')[0] for m in sys.modules}} & set({heavy!r}))))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, timeout=120
    )
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []


def test_studio_starts_without_the_u1_modules(tmp_path):
    """plan-u1 §14.1: until the Workspace has its rows, the server needs none of U1's modules
    (they import NumPy and the solver's models). launch.prepare builds the quick app."""
    u1 = ("routes", "contract", "capture", "jobs", "runner", "preview", "results", "binary")
    probe = (
        "import json, sys\nfrom pathlib import Path\nfrom etalon.studio import launch\n"
        "launch.GpuProbe = lambda: None\n"
        f"prepared = launch.prepare(Path({str(tmp_path)!r}), 0)\n"
        "assert not isinstance(prepared, int)\nprepared[1].close()\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('etalon.studio.'))))"
    )
    env = {**os.environ, "ETALON_CONFIG_DIR": str(tmp_path / "config")}
    out = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
        env=env,
    )
    loaded = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert "etalon.studio.staged" in loaded
    assert loaded.isdisjoint(f"etalon.studio.{name}" for name in u1)
