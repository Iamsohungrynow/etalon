"""The e2e fixture scripts behave as their Playwright tests expect (plan-u1 §7)."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from etalon.studio.binary import unpack
from etalon.studio.workspace import simulation_id
from tests.studio.conftest import make_client, make_state

FIXTURE = Path(__file__).resolve().parents[2] / "studio" / "e2e" / "fixtures" / "workspace"


@pytest.fixture
def fixture_client(tmp_path, config_dir):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ("misplaced_strip.py", "broken_script.py"):
        shutil.copyfile(FIXTURE / name, workspace / name)
    return make_client(make_state(workspace, config_dir))


def test_misplaced_strip_puts_silicon_off_the_source_line(fixture_client):
    sim_id = simulation_id("misplaced_strip.py")
    header, eps = unpack(fixture_client.get(f"/api/simulations/{sim_id}/permittivity").content)
    x0, x1, y0, y1 = header["extent"]
    x = np.linspace(x0, x1, header["shape"][0])
    y = np.linspace(y0, y1, header["shape"][1])
    column = eps[np.argmin(np.abs(x)), :]
    assert column[np.argmin(np.abs(y))] == pytest.approx(1.444**2, rel=1e-6)
    silicon = y[column > 10]
    assert silicon.min() == pytest.approx(0.36, abs=0.011)
    assert silicon.max() == pytest.approx(0.84, abs=0.011)
    spec = fixture_client.get(f"/api/simulations/{sim_id}/spec").json()
    assert spec["preview"]["structures"][0]["center"] == [0.0, 0.6, 0.0]
    assert spec["preview"]["sources"][0]["center"][1] == 0.05


def test_broken_script_fails_at_line_12(fixture_client):
    response = fixture_client.get(f"/api/simulations/{simulation_id('broken_script.py')}/spec")
    assert response.status_code == 422
    error = response.json()
    assert (error["code"], error["line"]) == ("script_error", 12)
    assert "KeyError: 'rnig'" in error["traceback"]
    assert "building the coupler" in error["stdout_tail"]
