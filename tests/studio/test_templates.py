"""Templates and "New from template" (plan-u1 §6, §13.2)."""

import json

import numpy as np
import pytest

from etalon.studio.binary import unpack
from etalon.studio.templates import TEMPLATE_DIR, TEMPLATE_IDS
from tests.studio.conftest import make_client, make_state


def test_four_templates_with_their_files(client):
    templates = client.get("/api/templates").json()
    assert templates == [
        {"id": "vacuum_pulse", "file": "vacuum_pulse.py"},
        {"id": "strip_waveguide", "file": "strip_waveguide.py"},
        {"id": "sharp_bend", "file": "sharp_bend.py"},
        {"id": "phc_waveguide", "file": "phc_waveguide.py"},
    ]
    for template in templates:
        assert (TEMPLATE_DIR / template["file"]).is_file()


def test_create_copies_the_template_and_returns_its_row(client, workspace):
    response = client.post("/api/simulations", json={"template": "sharp_bend", "name": "bend-01"})
    assert response.status_code == 201
    row = response.json()
    assert (row["name"], row["path"], row["status"]) == ("bend-01.py", "bend-01.py", "draft")
    assert row["job_id"] is None and row["last_result_id"] is None
    copied = (workspace / "bend-01.py").read_bytes()
    assert copied == (TEMPLATE_DIR / "sharp_bend.py").read_bytes()
    listed = client.get("/api/workspace").json()["simulations"]
    assert [r["id"] for r in listed] == [row["id"]]


def test_create_never_overwrites(client, workspace):
    (workspace / "mine.py").write_text("# my own work\n", encoding="utf-8")
    response = client.post("/api/simulations", json={"template": "vacuum_pulse", "name": "mine"})
    assert response.status_code == 409
    assert response.json()["code"] == "exists"
    assert (workspace / "mine.py").read_text(encoding="utf-8") == "# my own work\n"


@pytest.mark.parametrize(
    "name", ["", "a b", "../escape", "sub/dir", "x.py", "ring.", "名字", "a" * 65, "tab\t"]
)
def test_bad_names_are_422_bad_name(client, workspace, name):
    response = client.post("/api/simulations", json={"template": "vacuum_pulse", "name": name})
    assert response.status_code == 422
    assert response.json()["code"] == "bad_name"
    assert list(workspace.iterdir()) == []


def test_an_unknown_template_is_rejected(client):
    response = client.post("/api/simulations", json={"template": "ring", "name": "ok"})
    assert response.status_code == 422


@pytest.fixture(scope="module")
def specs(tmp_path_factory):
    """The spec of every template, each created through the API."""
    root = tmp_path_factory.mktemp("templates")
    workspace = root / "workspace"
    workspace.mkdir()
    client = make_client(make_state(workspace, root / "config"))
    found = {}
    for template_id in TEMPLATE_IDS:
        row = client.post(
            "/api/simulations", json={"template": template_id, "name": template_id}
        ).json()
        response = client.get(f"/api/simulations/{row['id']}/spec")
        assert response.status_code == 200, response.text
        permittivity = client.get(f"/api/simulations/{row['id']}/permittivity")
        found[template_id] = (response.json(), unpack(permittivity.content))
    return found


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_templates_are_2d_te_without_warnings(specs, template_id):
    spec, _ = specs[template_id]
    assert spec["warnings"] == []
    assert spec["preview"]["is_2d"]
    assert {s["component"] for s in spec["preview"]["sources"]} <= {"Ex", "Ey", "Hz"}
    estimate = spec["estimate"]
    # "in seconds on the GPU": at most ~100 k cells and ~6 k steps
    assert estimate["cells"] < 100_000 and estimate["steps"] < 6_000


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_templates_have_a_plane_monitor_for_the_field_viewer(specs, template_id):
    spec, _ = specs[template_id]
    geometries = {m["geometry"] for m in spec["preview"]["monitors"]}
    assert {"plane", "point"} <= geometries


def test_phc_line_defect_is_solid_silicon_between_air_holes(specs):
    spec, (header, eps) = specs["phc_waveguide"]
    assert spec["preview"]["background"]["name"] == "Si"
    assert [m["name"] for m in spec["preview"]["media"]] == ["air"]
    assert len(spec["preview"]["structures"]) == 12 * 6
    _, _, y0, y1 = header["extent"]
    y = np.linspace(y0, y1, header["shape"][1])
    line = eps[:, np.argmin(np.abs(y))]
    assert np.all(line == pytest.approx(3.476**2, rel=1e-6))  # the missing row
    row = eps[:, np.argmin(np.abs(y - 0.42))]
    assert row.min() == pytest.approx(1.0) and row.max() == pytest.approx(3.476**2, rel=1e-6)


def test_template_specs_round_trip(specs):
    for spec, _ in specs.values():
        json.dumps(spec["spec"])  # free-form, but JSON
