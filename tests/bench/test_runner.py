"""B6: the Meep subprocess command lines (never executed here) and the Meep result cache."""

import shutil

import pytest

from bench.config import load_config
from bench.run_meep_comparison import MeepRunner, meep_cache_state
from bench.schema import BENCH, MEEP_CODE_FILES, code_sha256
from tests.bench.fakes import default_spectra, device_result, run_record, write


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_native_command():
    runner = MeepRunner(kind="native", processes=6, micromamba="micromamba")
    assert runner.command("dc", "2d", ["--git-sha", "abc"]) == [
        "micromamba", "run", "-r", "/opt/micromamba", "-n", "etalon-meep",
        "mpirun", "-np", "6", "python", "-m", "mpi4py", "-m", "bench.meep.run_device",
        "dc", "--tier", "2d", "--git-sha", "abc",
    ]  # fmt: skip


def test_wsl_command(tmp_path):
    runner = MeepRunner(kind="wsl", processes=4, distro="Ubuntu-24.04")
    command = runner.command("ring", "3d", [], repo=tmp_path)
    assert command[:8] == [
        "wsl.exe",
        "-d",
        "Ubuntu-24.04",
        "-u",
        "root",
        "--cd",
        str(tmp_path),
        "--",
    ]
    assert command[8] == "/usr/local/bin/micromamba"
    assert command[-4:] == ["bench.meep.run_device", "ring", "--tier", "3d"]
    assert command[command.index("-np") + 1] == "4"


def copy_meep_code(root):
    """A bench tree holding the Meep code files, so code hashes match the real ones."""
    for name in MEEP_CODE_FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BENCH / name, target)


def test_cache_states(tmp_path, cfg):
    copy_meep_code(tmp_path)
    assert meep_cache_state(cfg, "2d", "dc", tmp_path) == "missing"
    run = run_record("meep-mpi", default_spectra(cfg, "dc"))
    fresh = device_result(cfg, "2d", "dc", "meep", [run], code_sha256=code_sha256(root=tmp_path))
    write(tmp_path, fresh)
    assert meep_cache_state(cfg, "2d", "dc", tmp_path) == "fresh"
    # a changed config number makes it stale
    changed = load_config(overrides=["devices.dc.gap=0.2"])
    assert meep_cache_state(changed, "2d", "dc", tmp_path) == "stale"
    # so does a change to the Meep script
    script = tmp_path / "meep" / "run_device.py"
    script.write_text(script.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    assert meep_cache_state(cfg, "2d", "dc", tmp_path) == "stale"
