"""Open in editor (never run the script) and calibrate (plan-u1 §13.2)."""

import pytest

from etalon.studio import editor, routes
from etalon.studio.throughput import ThroughputStore
from etalon.studio.workspace import simulation_id
from tests.studio.conftest import write_script


@pytest.mark.parametrize(
    ("command", "runs_python"),
    [
        (r'"C:\Windows\py.exe" "%L" %*', True),
        (r'"C:\Python312\python.exe" "%1" %*', True),
        (r"C:\Python312\pythonw.exe %1", True),
        (r'"C:\Users\me\AppData\Local\Programs\Microsoft VS Code\Code.exe" "%1"', False),
        (r'"C:\Program Files\JetBrains\PyCharm\bin\pycharm64.exe" "%1"', False),
        (r"C:\Windows\system32\NOTEPAD.EXE %1", False),
        ("", True),
        (None, True),
    ],
)
def test_an_interpreter_association_is_never_used(command, runs_python):
    assert editor.opens_with_interpreter(command) is runs_python


def test_open_calls_the_editor_with_the_script(client, workspace, monkeypatch):
    opened = []
    monkeypatch.setattr(editor, "open_in_editor", opened.append)
    script = write_script(workspace, "rings/ring.py")
    response = client.post(f"/api/simulations/{simulation_id('rings/ring.py')}/open")
    assert response.status_code == 204
    assert opened == [script]


def test_open_failure_is_500_open_failed(client, workspace, monkeypatch):
    def fail(path):
        raise OSError("no application is associated")

    monkeypatch.setattr(editor, "open_in_editor", fail)
    write_script(workspace, "ring.py")
    response = client.post(f"/api/simulations/{simulation_id('ring.py')}/open")
    assert response.status_code == 500
    assert response.json()["code"] == "open_failed"


def test_open_unknown_simulation_is_404(client):
    assert client.post("/api/simulations/000000000000/open").status_code == 404


def test_calibrate_measures_the_cpu_and_feeds_the_estimate(
    client, workspace, config_dir, monkeypatch
):
    monkeypatch.setattr(routes, "CALIBRATION_SECONDS", 0.3)
    client.put("/api/settings", json={**client.get("/api/settings").json(), "backend": "cpu"})
    response = client.post("/api/calibrate")
    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "cpu"
    assert body["cells_per_s"] > 1e5
    assert body["device"]
    basis, cells_per_s = ThroughputStore(config_dir).lookup("cpu")
    assert basis == "calibration"
    assert cells_per_s == body["cells_per_s"]
