"""S6–S8: the workspace scan, sidecar status, and speed."""

import hashlib
import os
import sys
import time

import pytest

from etalon.studio.workspace import scan, simulation_id
from tests.studio.conftest import sha256_of, write_script, write_status

DONE = {
    "status": "done",
    "started_at": "2026-10-16T05:59:00Z",
    "finished_at": "2026-10-16T06:02:12Z",
    "backend": "cuda:0",
    "device": "NVIDIA GeForce RTX 4060 Ti",
    "cells": 42_300_000,
    "wall_time_s": 192.0,
}


# S6 ----------------------------------------------------------------------------------
def test_scan_is_recursive_and_skips_hidden_private_and_environments(workspace):
    for relative in [
        "straight_wg.py",
        "rings/ring_r10_g200.py",
        "rings/sweeps/ring_r10_g180.py",
        "_private.py",
        "__init__.py",
        "_helpers/util.py",
        "__pycache__/cached.py",
        ".hidden/secret.py",
        ".etalon/straight_wg.py/notes.py",
        "node_modules/pkg/index.py",
        "lib/site-packages/mod.py",
        "venv/lib/site.py",
        "notes.txt",
        "data.pyc",
    ]:
        write_script(workspace, relative)
    (workspace / "venv" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
    paths = [row.path for row in scan(workspace).simulations]
    assert paths == ["rings/ring_r10_g200.py", "rings/sweeps/ring_r10_g180.py", "straight_wg.py"]


def test_rows_are_sorted_case_insensitively(workspace):
    for name in ["b.py", "A.py", "c.py", "B2.py"]:
        write_script(workspace, name)
    assert [row.name for row in scan(workspace).simulations] == ["A.py", "b.py", "B2.py", "c.py"]


def test_ids_are_stable_unique_and_url_safe(workspace):
    write_script(workspace, "rings/ring.py")
    write_script(workspace, "ring.py")
    rows = scan(workspace).simulations
    expected = hashlib.sha256(b"rings/ring.py").hexdigest()[:12]
    assert {row.path: row.id for row in rows}["rings/ring.py"] == expected
    assert simulation_id("rings/ring.py") == expected
    assert len({row.id for row in rows}) == 2
    assert all(row.id.isalnum() and len(row.id) == 12 for row in rows)
    assert [row.id for row in scan(workspace).simulations] == [row.id for row in rows]


def test_paths_use_posix_separators(workspace):
    write_script(workspace, "a/b/c.py")
    assert scan(workspace).simulations[0].path == "a/b/c.py"


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_directories_are_not_followed(workspace, tmp_path):
    outside = tmp_path / "outside"
    write_script(outside, "far.py")
    os.symlink(outside, workspace / "link", target_is_directory=True)
    os.symlink(workspace, workspace / "loop", target_is_directory=True)
    write_script(workspace, "here.py")
    assert [row.path for row in scan(workspace).simulations] == ["here.py"]


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan(tmp_path / "gone")


def test_missing_folder_is_a_404_with_a_code(client, workspace):
    workspace.rmdir()
    response = client.get("/api/workspace")
    assert response.status_code == 404
    assert response.json()["code"] == "workspace_missing"


# S7 ----------------------------------------------------------------------------------
def test_no_sidecar_is_a_draft(workspace):
    write_script(workspace, "draft.py")
    row = scan(workspace).simulations[0]
    assert row.status == "draft"
    assert row.last_run is None and row.cells is None and not row.stale


def test_done_row_carries_the_run(workspace):
    script = write_script(workspace, "done.py")
    write_status(script, {**DONE, "script_sha256": sha256_of(script)})
    row = scan(workspace).simulations[0]
    assert row.status == "done"
    assert row.last_run is not None and row.last_run.isoformat() == "2026-10-16T06:02:12+00:00"
    assert (row.backend, row.device, row.cells, row.wall_time_s) == (
        "cuda:0",
        "NVIDIA GeForce RTX 4060 Ti",
        42_300_000,
        192.0,
    )
    assert not row.stale


def test_changed_script_is_stale(workspace):
    script = write_script(workspace, "edited.py")
    write_status(script, {**DONE, "script_sha256": sha256_of(script)})
    script.write_text("import etalon as et  # edited\n", encoding="utf-8")
    assert scan(workspace).simulations[0].stale


def test_running_row_reports_progress_and_is_never_stale(workspace):
    script = write_script(workspace, "running.py")
    write_status(
        script,
        {
            "status": "running",
            "started_at": "2026-10-16T06:10:00Z",
            "step": 11_000,
            "total_steps": 26_400,
            "eta_s": 120.0,
            "script_sha256": "0" * 64,
        },
    )
    row = scan(workspace).simulations[0]
    assert row.status == "running"
    assert (row.step, row.total_steps, row.eta_s) == (11_000, 26_400, 120.0)
    assert row.last_run is not None and row.last_run.isoformat() == "2026-10-16T06:10:00+00:00"
    assert not row.stale


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_failed_and_cancelled(workspace, status):
    script = write_script(workspace, "x.py")
    write_status(script, {"status": status, "finished_at": "2026-10-15T09:00:00Z"})
    assert scan(workspace).simulations[0].status == status


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("{not json", "invalid_json"),
        ('{"status": "exploded"}', "invalid_fields"),
        ('{"status": "done", "cells": "many"}', "invalid_fields"),
        ('["done"]', "invalid_fields"),
        ('{"status": "done", "finished_at": "2026-10-16T06:02:12"}', "invalid_fields"),
    ],
)
def test_bad_sidecar_is_unknown_with_a_reason(workspace, raw, reason):
    script = write_script(workspace, "bad.py")
    write_status(script, raw)
    write_script(workspace, "fine.py")
    rows = {row.name: row for row in scan(workspace).simulations}
    assert (rows["bad.py"].status, rows["bad.py"].status_reason) == ("unknown", reason)
    assert rows["fine.py"].status == "draft"


def test_api_returns_the_scan(client, workspace):
    write_script(workspace, "a.py")
    body = client.get("/api/workspace").json()
    assert body["folder"] == str(workspace)
    assert body["truncated"] is False
    assert [row["name"] for row in body["simulations"]] == ["a.py"]


# S8 ----------------------------------------------------------------------------------
def test_fifty_scripts_scan_fast(workspace):
    for i in range(50):
        script = write_script(workspace, f"group_{i % 5}/device_{i:02d}.py", f"# {i}\n")
        if i % 2:
            write_status(script, {**DONE, "script_sha256": sha256_of(script)})
    best = min(_timed(lambda: scan(workspace)) for _ in range(3))
    assert len(scan(workspace).simulations) == 50
    assert best < 0.1, f"scan of 50 scripts took {best * 1e3:.0f} ms"


def test_scan_stops_at_the_limit(workspace):
    for i in range(12):
        write_script(workspace, f"s{i:02d}.py")
    result = scan(workspace, limit=10)
    assert result.truncated and len(result.simulations) == 10
    assert not scan(workspace, limit=12).truncated


def _timed(call):
    start = time.perf_counter()
    call()
    return time.perf_counter() - start


# U1: job and result ids, and runs that stopped sending heartbeats ---------------------
def test_last_result_id_and_job_id(workspace):
    script = write_script(workspace, "ring.py")
    write_status(
        script, {**DONE, "last_run": "20261016T060200Z", "last_result": "20261016T050000Z"}
    )
    sim_id = simulation_id("ring.py")
    (row,) = scan(workspace, jobs={sim_id: "abc123"}).simulations
    assert row.last_result_id == f"{sim_id}~20261016T050000Z"
    assert row.job_id == "abc123"
    (row,) = scan(workspace).simulations
    assert row.job_id is None


@pytest.mark.parametrize(
    ("heartbeat_age_s", "job", "status", "reason"),
    [
        (5, None, "running", None),
        (120, None, "unknown", "interrupted"),
        (120, "abc123", "running", None),  # this server still runs it
        (None, None, "running", None),  # no heartbeat: a U0-era sidecar
    ],
)
def test_a_running_sidecar_without_heartbeat_is_interrupted(
    workspace, heartbeat_age_s, job, status, reason
):
    from datetime import UTC, datetime, timedelta

    script = write_script(workspace, "ring.py")
    raw = {"status": "running", "started_at": "2026-10-16T05:59:00Z", "step": 10, "total_steps": 99}
    if heartbeat_age_s is not None:
        beat = datetime.now(UTC) - timedelta(seconds=heartbeat_age_s)
        raw["heartbeat_at"] = beat.isoformat()
    write_status(script, raw)
    jobs = {simulation_id("ring.py"): job} if job else None
    (row,) = scan(workspace, jobs=jobs).simulations
    assert (row.status, row.status_reason) == (status, reason)
