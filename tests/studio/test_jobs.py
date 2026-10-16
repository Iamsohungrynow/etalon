"""The job runner on the CPU (plan-u1 §8): progress, energy, snapshots, cancel, failures."""

import json
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import etalon as et
from etalon.grid.materials import permittivity_on_nodes
from etalon.studio.binary import unpack
from etalon.studio.runner import (
    NumericalInstability,
    downsample,
    field_energy,
    suggestion_for,
)
from etalon.studio.workspace import simulation_id
from tests.studio.conftest import TOKEN, make_client, make_state, write_script

# 624 × 64 cells: the snapshot is downsampled along x (stride 3) but not along y.
RUN_SCRIPT = """\
import etalon as et

sim = et.Simulation(
    size=(12.0, 0.8, 0.0),
    grid=et.UniformGrid(dl=0.02),
    sources=[
        et.PointSource(
            center=(-5.0, 0.0, 0.0),
            component="Hz",
            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.5, amplitude=AMPLITUDE),
        )
    ],
    monitors=[
        et.DFTMonitor(name="probe", center=(-4.0, 0.0, 0.0), wavelengths=[1.5, 1.55, 1.6],
                      components=["Hz"]),
        et.DFTMonitor(name="line", size=(10.0, 0.0, 0.0), wavelengths=[1.55], components=["Hz"]),
    ],
    run_time=RUN_TIME,
)
print("before run")
result = sim.run()
print("after run", abs(complex(result["probe"]["Hz"].values[1])) > 0)
"""


def run_script(run_time: float = 100e-15, amplitude: float = 1.0) -> str:
    return RUN_SCRIPT.replace("RUN_TIME", repr(run_time)).replace("AMPLITUDE", repr(amplitude))


@pytest.fixture
def cpu_client(workspace, config_dir):
    state = make_state(workspace, config_dir)
    state.settings.put(
        state.settings.get().model_copy(update={"backend": "cpu", "live_snapshots": True})
    )
    client = make_client(state)
    client.state = state  # type: ignore[attr-defined]
    yield client
    state.jobs.shutdown()


def socket(client: TestClient, job_id: str, token: str = TOKEN, origin: str | None = None):
    headers = {"origin": origin} if origin else {}
    return client.websocket_connect(
        f"ws://127.0.0.1:8787/api/jobs/{job_id}",
        subprotocols=["etalon.v1", f"token.{token}"],
        headers=headers,
    )


def collect(client: TestClient, job_id: str) -> list[tuple[float, object]]:
    """Every frame until ``done``, with its arrival time."""
    frames: list[tuple[float, object]] = []
    with socket(client, job_id) as ws:
        assert ws.accepted_subprotocol == "etalon.v1"
        while True:
            frame = ws.receive()
            now = time.monotonic()
            if frame.get("bytes") is not None:
                frames.append((now, unpack(frame["bytes"])))
                continue
            message = json.loads(frame["text"])
            frames.append((now, message))
            if message["type"] == "done":
                return frames


def messages(frames, kind):
    return [m for _, m in frames if isinstance(m, dict) and m["type"] == kind]


def start(client, workspace, text, name="run.py"):
    write_script(workspace, name, text)
    sim_id = simulation_id(name)
    response = client.post(f"/api/simulations/{sim_id}/run")
    assert response.status_code == 202, response.text
    return sim_id, response.json()


def test_a_run_on_the_cpu(cpu_client, workspace):
    sim_id, job = start(cpu_client, workspace, run_script())
    assert job["result_id"].startswith(f"{sim_id}~")
    frames = collect(cpu_client, job["job_id"])

    # started, then history, then live messages (plan-u1 §13.3)
    kinds = [m["type"] if isinstance(m, dict) else "snapshot" for _, m in frames]
    assert kinds[0] in ("started", "history")
    (started,) = messages(frames, "started")
    assert started["grid"] == [624, 64]
    assert started["backend"] == "cpu" and started["snapshots"] is True
    spec = cpu_client.get(f"/api/simulations/{sim_id}/spec").json()
    assert started["total"] == spec["preview"]["grid"]["steps"] == 2142

    # progress at most 4 per second, energy finite and decaying after the pulse
    progress = [(t, m) for t, m in frames if isinstance(m, dict) and m["type"] == "progress"]
    assert len(progress) >= 3
    times = [t for t, _ in progress]
    span = times[-1] - times[0]
    assert len(progress) - 1 <= 4 * span + 2
    energy = np.array([m["energy"] for _, m in progress])
    assert np.all(np.isfinite(energy)) and energy.max() > 0
    assert energy[-1] < 1e-2 * energy.max()
    steps = [m["step"] for _, m in progress]
    assert steps == sorted(steps) and steps[-1] == started["total"]
    assert progress[-1][1]["eta_s"] == 0

    # snapshots: Hz downsampled to at most 256 per axis, with their own extent
    snapshots = [m for _, m in frames if isinstance(m, tuple)]
    assert snapshots
    for header, data in snapshots:
        assert header["kind"] == "snapshot" and header["component"] == "Hz"
        assert header["shape"] == [208, 64] and data.shape == (208, 64)
        x0, x1, y0, y1 = header["extent"]
        assert -6.24 < x0 < x1 < 6.24 and -0.64 < y0 < y1 < 0.64
    assert np.abs(snapshots[-2][1]).max() > 0

    # the script ran on after run() with the real result
    lines = [m["line"] for m in messages(frames, "log")]
    history_lines = [line["line"] for h in messages(frames, "history") for line in h["log"]]
    assert "after run True" in lines + history_lines

    (done,) = messages(frames, "done")
    assert done == {
        "type": "done",
        "status": "done",
        "result_id": job["result_id"],
        "error": None,
        "suggestion": None,
    }
    folder = workspace / ".etalon" / "run.py" / "runs" / job["result_id"].split("~")[1]
    assert {p.name for p in folder.iterdir()} == {"meta.json", "log.txt", "result.npz"}
    assert "before run" in (folder / "log.txt").read_text(encoding="utf-8")
    status = json.loads((workspace / ".etalon" / "run.py" / "status.json").read_text())
    assert status["status"] == "done"
    assert status["step"] == status["total_steps"] == started["total"]
    rows = cpu_client.get("/api/workspace").json()["simulations"]
    (row,) = [r for r in rows if r["id"] == sim_id]
    assert row["status"] == "done" and row["backend"] == "cpu"
    assert row["last_result_id"] == job["result_id"] and row["job_id"] is None


def test_cancel_within_2_s_keeps_partial_data(cpu_client, workspace):
    sim_id, job = start(cpu_client, workspace, run_script(run_time=20e-12))
    with socket(cpu_client, job["job_id"]) as ws:
        while True:  # wait until it steps
            frame = ws.receive()
            if frame.get("text") and json.loads(frame["text"])["type"] == "progress":
                break
        again = cpu_client.post(f"/api/simulations/{sim_id}/run")
        assert again.status_code == 409
        assert again.json() == {
            "code": "already_running",
            "message": again.json()["message"],
            "job_id": job["job_id"],
        }
        assert cpu_client.get(f"/api/results/{job['result_id']}").json()["code"] == "running"
        rows = cpu_client.get("/api/workspace").json()["simulations"]
        assert [r["job_id"] for r in rows if r["id"] == sim_id] == [job["job_id"]]
        asked = time.monotonic()
        response = cpu_client.delete(f"/api/jobs/{job['job_id']}")
        assert response.status_code == 202 and response.json() == {"status": "cancelling"}
        while True:
            frame = ws.receive()
            if frame.get("text") and json.loads(frame["text"])["type"] == "done":
                done = json.loads(frame["text"])
                break
    assert time.monotonic() - asked < 2.0
    assert done["status"] == "cancelled"
    assert done["result_id"] == job["result_id"]
    meta = cpu_client.get(f"/api/results/{job['result_id']}").json()
    assert meta["status"] == "cancelled"
    assert 0 < meta["steps"] < 20e-12 / meta["dt_s"]
    spectra = cpu_client.get(f"/api/results/{job['result_id']}/spectra/probe").json()
    assert len(spectra["components"]["Hz"]["re"]) == 3
    assert cpu_client.delete(f"/api/jobs/{job['job_id']}").json()["code"] == "not_running"


def test_a_failing_script_reports_its_traceback(cpu_client, workspace):
    text = "import etalon as et\nprint('starting')\nraise ValueError('no such gap')\n"
    _, job = start(cpu_client, workspace, text)
    frames = collect(cpu_client, job["job_id"])
    assert messages(frames, "started") == []
    (done,) = messages(frames, "done")
    assert done["status"] == "failed" and done["result_id"] is None
    assert done["error"]["line"] == 3
    assert done["error"]["message"] == "no such gap"
    assert "ValueError: no such gap" in done["error"]["traceback"]
    assert done["suggestion"] is None
    history = messages(frames, "history")
    logged = [line["line"] for line in history[0]["log"]] + [
        m["line"] for m in messages(frames, "log")
    ]
    assert "starting" in logged
    assert cpu_client.get(f"/api/results/{job['result_id']}").json()["code"] == "no_result"
    status = json.loads((workspace / ".etalon" / "run.py" / "status.json").read_text())
    assert status["status"] == "failed"


def test_an_unsupported_simulation_suggests_why(cpu_client, workspace):
    text = run_script().replace(
        'component="Hz",\n            pulse', 'component="Ez",\n            pulse'
    )
    _, job = start(cpu_client, workspace, text)
    (done,) = messages(collect(cpu_client, job["job_id"]), "done")
    assert (done["status"], done["suggestion"]) == ("failed", "unsupported")
    assert "TM" in done["error"]["message"]


def test_diverging_fields_suggest_nan(cpu_client, workspace):
    _, job = start(cpu_client, workspace, run_script(amplitude=1e36))
    (done,) = messages(collect(cpu_client, job["job_id"]), "done")
    assert (done["status"], done["suggestion"]) == ("failed", "nan")


def test_a_late_socket_gets_the_whole_story(cpu_client, workspace):
    _, job = start(cpu_client, workspace, run_script(run_time=30e-15))
    collect(cpu_client, job["job_id"])
    frames = collect(cpu_client, job["job_id"])
    kinds = [m["type"] if isinstance(m, dict) else "snapshot" for _, m in frames]
    assert kinds == ["started", "history", "snapshot", "done"]
    history = frames[1][1]
    assert history["progress"] and history["progress"][-1]["step"] == frames[0][1]["total"]
    assert any(line["line"] == "before run" for line in history["log"])


@pytest.mark.parametrize(
    ("token", "origin"),
    [("wrong", None), ("", None), (TOKEN, "http://evil.example"), (TOKEN, "null")],
)
def test_socket_needs_the_token_and_studios_origin(workspace, config_dir, token, origin):
    client = make_client(make_state(workspace, config_dir), token=None)
    with pytest.raises(WebSocketDisconnect), socket(client, "anything", token=token, origin=origin):
        pass


def test_socket_with_studios_origin_reaches_the_route(workspace, config_dir):
    client = make_client(make_state(workspace, config_dir), token=None)
    # An unknown job is closed by the route itself, after the guard let it through.
    with (
        pytest.raises(WebSocketDisconnect) as raised,
        socket(client, "nope", origin="http://127.0.0.1:8787"),
    ):
        pass
    assert raised.value.reason == "job_not_found"


def test_cancel_unknown_job_is_404(client):
    assert client.delete("/api/jobs/nope").json()["code"] == "job_not_found"


# Pieces of the runner -------------------------------------------------------------------
def test_field_energy_uses_the_solvers_permittivity():
    sim = et.Simulation(
        size=(1.0, 0.6, 0.0),
        structures=[et.Box(size=(0.4, 0.2, 0.0), medium=et.Medium(n=2.0))],
        grid=et.UniformGrid(dl=0.05),
        sources=[
            et.PointSource(
                center=(0, 0, 0),
                component="Hz",
                pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.3),
            )
        ],
        run_time=1e-15,
        backend="numpy",
    )
    from etalon.fdtd.solver import FDTDSolver

    solver = FDTDSolver(sim)
    solver.state.ex[...] = 2.0  # V/m
    solver.state.hz[...] = 1.0  # A/m
    eps = permittivity_on_nodes(sim, solver.grid)["Ex"]
    area = (0.05e-6) ** 2
    expected = (
        0.5
        * area
        * (et.constants.EPSILON_0 * 4.0 * eps.sum() + et.constants.MU_0 * solver.state.hz.size)
    )
    assert field_energy(solver) == pytest.approx(expected, rel=1e-5)


def test_downsample_takes_block_means_up_to_256_per_axis():
    field = np.arange(600 * 10, dtype=np.float32).reshape(600, 10)
    blocks, sx, sy = downsample(field, np)
    assert (sx, sy) == (3, 1)
    assert blocks.shape == (200, 10)
    assert blocks[0, 0] == pytest.approx(field[0:3, 0].mean())
    small, sx, sy = downsample(np.ones((256, 256), np.float32), np)
    assert small.shape == (256, 256) and (sx, sy) == (1, 1)


class OutOfMemoryError(Exception):
    """Stands in for cupy.cuda.memory.OutOfMemoryError, matched by name."""


@pytest.mark.parametrize(
    ("error", "suggestion"),
    [
        (MemoryError(), "out_of_memory"),
        (OutOfMemoryError("out of memory allocating 8 GB"), "out_of_memory"),
        (RuntimeError("cudaErrorMemoryAllocation: out of memory"), "out_of_memory"),
        (NumericalInstability("fields stopped being finite"), "nan"),
        (NotImplementedError("3D simulations arrive in M1"), "unsupported"),
        (ValueError("anything else"), None),
    ],
)
def test_suggestions(error, suggestion):
    assert suggestion_for(error) == suggestion


def test_runner_never_loads_heavy_modules_into_the_server():
    import subprocess
    import sys

    code = (
        "import sys, etalon.studio.server\n"
        "print([m for m in ('scipy', 'xarray', 'matplotlib', 'cupy') if m in sys.modules])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    ).stdout
    assert out.strip() == "[]"
