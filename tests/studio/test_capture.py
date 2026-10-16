"""Spec capture (plan-u1 §2, §8): the user's script runs in a child process up to run()."""

import textwrap
import time

import pytest

from etalon.studio.capture import SpecCache, tail
from etalon.studio.errors import ModelError
from etalon.studio.workspace import simulation_id
from tests.studio.conftest import write_script

SIM = """\
import etalon as et

sim = et.Simulation(
    size=(2.0, 1.0, 0.0),
    grid=et.UniformGrid(dl=0.05),
    sources=[
        et.PointSource(
            center=(0.0, 0.0, 0.0),
            component="Hz",
            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.3),
        )
    ],
    run_time=20e-15,
)
"""


def script_text(body: str) -> str:
    return SIM + textwrap.dedent(body)


def capture(workspace, text, timeout_s=60.0):
    script = write_script(workspace, "sim.py", text)
    return SpecCache(timeout_s=timeout_s).get(script, workspace)


def test_run_is_captured_and_the_script_stops_there(workspace):
    captured = capture(
        workspace,
        script_text(
            """
            print("before run")
            sim.run()
            open("after_run.txt", "w").write("the script went on")
            """
        ),
    )
    assert captured.spec["size"] == [2.0, 1.0, 0.0]
    assert captured.spec["sources"][0]["component"] == "Hz"
    assert "before run" in captured.stdout_tail
    assert not (workspace / "after_run.txt").exists()


def test_without_run_the_module_level_simulation_is_used(workspace):
    captured = capture(workspace, script_text('print("no run here")\n'))
    assert captured.spec["grid"]["dl"] == 0.05
    assert "no run here" in captured.stdout_tail


def test_the_first_run_wins(workspace):
    text = script_text(
        """
        sim.run()
        sim.model_copy(update={"run_time": 1e-15}).run()
        """
    )
    assert capture(workspace, text).spec["run_time"] == 20e-15


def test_the_script_runs_in_the_workspace_and_imports_its_neighbours(workspace):
    write_script(workspace, "sub/_helper.py", "VALUE = 42\n")
    script = write_script(
        workspace,
        "sub/sim.py",
        "import os\nimport _helper\nprint('cwd', os.getcwd(), _helper.VALUE)\n" + SIM,
    )
    captured = SpecCache().get(script, workspace)
    assert f"cwd {workspace.resolve()} 42" in captured.stdout_tail


def test_an_exception_reports_its_line_and_traceback(workspace):
    lines = SIM.count("\n")
    with pytest.raises(ModelError) as raised:
        capture(workspace, script_text('print("almost")\nraise ValueError("bad gap")\n'))
    assert raised.value.status == 422
    error = raised.value.body.model_dump()
    assert error["code"] == "script_error"
    assert error["line"] == lines + 2
    assert "ValueError: bad gap" in error["traceback"]
    assert error["message"] == "bad gap"
    assert "almost" in error["stdout_tail"]
    assert "etalon\\studio\\runner.py" not in error["traceback"].split("sim.py")[0]


def test_an_invalid_simulation_points_at_its_line(workspace):
    text = "import etalon as et\n\nx = 1\nsim = et.Simulation(size=(1, 1, 0))\n"
    with pytest.raises(ModelError) as raised:
        capture(workspace, text)
    error = raised.value.body.model_dump()
    assert error["code"] == "script_error"
    assert error["line"] == 4
    assert "ValidationError" in error["traceback"]


def test_a_syntax_error_reports_its_line(workspace):
    with pytest.raises(ModelError) as raised:
        capture(workspace, "import etalon as et\n\nsim = et.Simulation(\n")
    error = raised.value.body.model_dump()
    assert error["code"] == "script_error"
    assert error["line"] == 3
    assert "SyntaxError" in error["traceback"]


def test_a_script_without_simulation(workspace):
    with pytest.raises(ModelError) as raised:
        capture(workspace, "import etalon as et\nx = 1\n")
    assert raised.value.body.model_dump()["code"] == "no_simulation"


def test_a_runaway_script_times_out(workspace):
    start = time.monotonic()
    with pytest.raises(ModelError) as raised:
        capture(workspace, "print('waiting', flush=True)\nimport time\ntime.sleep(60)\n", 3.0)
    assert time.monotonic() - start < 20
    error = raised.value.body.model_dump()
    assert error["code"] == "script_timeout"
    assert "waiting" in error["stdout_tail"]


def test_an_unchanged_script_is_captured_once(workspace):
    script = write_script(workspace, "sim.py", SIM)
    cache = SpecCache()
    first = cache.get(script, workspace)
    assert cache.get(script, workspace) is first
    assert cache.captures == 1
    script.write_text(SIM.replace("20e-15", "30e-15"), encoding="utf-8")
    assert cache.get(script, workspace).spec["run_time"] == 30e-15
    assert cache.captures == 2


def test_failures_are_not_cached(workspace):
    script = write_script(workspace, "sim.py", "raise RuntimeError('missing data file')\n")
    cache = SpecCache()
    for _ in range(2):
        with pytest.raises(ModelError):
            cache.get(script, workspace)
    assert cache.captures == 2


def test_tail_keeps_the_last_lines():
    text = "\n".join(f"line {i}" for i in range(100))
    assert tail(text, lines=3) == "line 97\nline 98\nline 99"
    assert len(tail("x" * 20_000)) == 8000


# Through the API ----------------------------------------------------------------------
def test_spec_endpoint_answers_with_preview_estimate_and_warnings(client, workspace):
    write_script(workspace, "sim.py", SIM + "sim.run()\n")
    response = client.get(f"/api/simulations/{simulation_id('sim.py')}/spec")
    assert response.status_code == 200
    body = response.json()
    assert len(body["script_sha256"]) == 64
    assert body["preview"]["grid"]["nx"] == 40 + 24
    assert body["estimate"]["basis"] == "unknown"
    assert body["estimate"]["seconds"] is None
    # 12 cells of 0.05 µm = 0.6 µm of PML, less than λ/2 = 0.775 µm in vacuum
    assert [w["code"] for w in body["warnings"]] == ["pml_thin"]


def test_spec_endpoint_422_carries_the_script_error(client, workspace):
    write_script(workspace, "broken.py", "x = 1\nraise KeyError('gap')\n")
    response = client.get(f"/api/simulations/{simulation_id('broken.py')}/spec")
    assert response.status_code == 422
    assert response.json()["code"] == "script_error"
    assert response.json()["line"] == 2


def test_spec_of_an_unknown_simulation_is_404(client):
    response = client.get("/api/simulations/000000000000/spec")
    assert response.status_code == 404
    assert response.json()["code"] == "simulation_not_found"
