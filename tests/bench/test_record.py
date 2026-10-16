"""B9: results/<sha>.json sections and the git dirty flag."""

import json
import shutil
import subprocess

import pytest

from bench.record import git_sha, update_record


def test_sections_merge(tmp_path):
    update_record("abc", "m0", {"a": 1}, tmp_path)
    update_record("abc", "meep_comparison", {"b": 2}, tmp_path)
    update_record("abc", "m0", {"a": 3}, tmp_path)
    record = json.loads((tmp_path / "abc.json").read_text(encoding="utf-8"))
    assert record == {"git_sha": "abc", "m0": {"a": 3}, "meep_comparison": {"b": 2}}


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_dirty_flag_ignores_bench_outputs(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a.txt").write_text("x")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    sha = git_sha(tmp_path)
    assert len(sha) >= 7 and not sha.endswith("-dirty")
    for output in (
        "bench/results/x.md",
        "bench/meep/out/2d/dc.json",
        "bench/etalon/out/2d/dc.json",
    ):
        path = tmp_path / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    assert git_sha(tmp_path) == sha
    (tmp_path / "a.txt").write_text("changed")
    assert git_sha(tmp_path) == sha + "-dirty"
