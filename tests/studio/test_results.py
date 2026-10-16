"""Results endpoints (plan-u1 §13.4) on the recorded fixture run (studio/e2e/fixtures/record.py)."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from etalon.studio.binary import unpack
from etalon.studio.templates import TEMPLATE_DIR
from etalon.studio.workspace import simulation_id
from tests.studio.conftest import make_client, make_state

FIXTURE = Path(__file__).resolve().parents[2] / "studio" / "e2e" / "fixtures" / "workspace"
SIM_ID = simulation_id("phc_waveguide.py")


def recorded_folder() -> Path:
    (folder,) = (FIXTURE / ".etalon" / "phc_waveguide.py" / "runs").iterdir()
    return folder


RESULT_ID = f"{SIM_ID}~{recorded_folder().name}"


@pytest.fixture
def copy(tmp_path):
    """The fixture workspace's recorded run, copied so a test may change the script."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    shutil.copyfile(FIXTURE / "phc_waveguide.py", workspace / "phc_waveguide.py")
    shutil.copytree(
        FIXTURE / ".etalon" / "phc_waveguide.py", workspace / ".etalon" / "phc_waveguide.py"
    )
    return workspace


@pytest.fixture
def results(copy, config_dir):
    return make_client(make_state(copy, config_dir))


@pytest.fixture(scope="module")
def npz():
    with np.load(recorded_folder() / "result.npz") as data:
        return {key: data[key] for key in data.files}


def test_the_fixture_script_is_the_template():
    assert (FIXTURE / "phc_waveguide.py").read_bytes() == (
        TEMPLATE_DIR / "phc_waveguide.py"
    ).read_bytes()


def test_the_fixture_stays_small():
    assert (recorded_folder() / "result.npz").stat().st_size < 2_000_000


def test_meta(results):
    response = results.get(f"/api/results/{RESULT_ID}")
    assert response.status_code == 200
    meta = response.json()
    assert meta["result_id"] == RESULT_ID and meta["simulation_id"] == SIM_ID
    assert (meta["status"], meta["backend"], meta["precision"]) == ("done", "cpu", "single")
    assert meta["grid"] == {"nx": 276, "ny": 171, "dx": 0.02, "dy": pytest.approx(0.02)}
    assert meta["steps"] == 5354
    assert meta["wall_time_s"] > 0 and meta["cells_per_s"] > 0
    assert meta["stale"] is False
    assert meta["etalon_version"] == "0.0.1"
    assert len(meta["preview"]["structures"]) == 72
    monitors = {m["name"]: m for m in meta["monitors"]}
    assert monitors["field"]["geometry"] == "plane"
    assert monitors["field"]["components"] == ["Ex", "Ey", "Hz"]
    assert monitors["field"]["wavelengths_um"] == [1.5, 1.55, 1.6]
    assert monitors["field"]["shape"] == [230, 100]  # Ex's nodes
    assert monitors["in"] == {
        "name": "in",
        "geometry": "point",
        "components": ["Hz"],
        "wavelengths_um": [1.5, 1.55, 1.6],
        "shape": None,
        "extent": None,
    }


def test_the_workspace_row_points_at_the_result(results):
    (row,) = results.get("/api/workspace").json()["simulations"]
    assert (row["status"], row["stale"], row["last_result_id"]) == ("done", False, RESULT_ID)


def test_changing_the_script_makes_the_result_stale(results, copy):
    script = copy / "phc_waveguide.py"
    script.write_bytes(script.read_bytes().replace(b"a = 0.42", b"a = 0.43"))
    assert results.get(f"/api/results/{RESULT_ID}").json()["stale"] is True
    (row,) = results.get("/api/workspace").json()["simulations"]
    assert row["stale"] is True


@pytest.mark.parametrize("component", ["Ex", "Ey", "Hz"])
@pytest.mark.parametrize("index", [0, 2])
def test_field_slice_is_the_stored_array(results, npz, component, index):
    url = f"/api/results/{RESULT_ID}/fields/field?component={component}&wavelength_index={index}"
    response = results.get(url + "&quantity=real")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    header, data = unpack(response.content)
    stored = npz[f"m0.{component}"][:, :, index]
    assert data.dtype == np.dtype("<f4")
    assert header["shape"] == list(stored.shape)
    np.testing.assert_array_equal(data, stored.real.astype(np.float32))
    x, y = npz[f"m0.{component}.x"], npz[f"m0.{component}.y"]
    assert header["extent"] == pytest.approx([x[0], x[-1], y[0], y[-1]])
    assert header["kind"] == "field" and header["component"] == component
    assert header["wavelength_um"] == [1.5, 1.55, 1.6][index]
    assert header["unit"] == ("A·s/m" if component == "Hz" else "V·s/m")
    assert (header["min"], header["max"]) == (data.min(), data.max())


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [("abs", np.abs), ("real", np.real), ("imag", np.imag), ("phase", np.angle)],
)
def test_field_quantities(results, npz, quantity, expected):
    response = results.get(
        f"/api/results/{RESULT_ID}/fields/field?component=Hz&quantity={quantity}"
    )
    header, data = unpack(response.content)
    np.testing.assert_array_equal(data, expected(npz["m0.Hz"][:, :, 0]).astype(np.float32))
    assert header["quantity"] == quantity
    assert header["unit"] == ("rad" if quantity == "phase" else "A·s/m")


def test_field_defaults_to_abs_of_the_first_component_at_the_first_wavelength(results, npz):
    header, data = unpack(results.get(f"/api/results/{RESULT_ID}/fields/field").content)
    assert (header["component"], header["quantity"], header["wavelength_um"]) == ("Ex", "abs", 1.5)
    np.testing.assert_array_equal(data, np.abs(npz["m0.Ex"][:, :, 0]).astype(np.float32))


@pytest.mark.parametrize(
    ("url", "status", "code"),
    [
        ("/fields/nope", 404, "monitor_not_found"),
        ("/fields/field?component=Ez", 404, "component_not_found"),
        ("/fields/field?wavelength_index=3", 404, "wavelength_not_found"),
        ("/fields/field?wavelength_index=-1", 404, "wavelength_not_found"),
        ("/fields/in", 409, "point_monitor"),
        ("/spectra/field", 409, "not_point_monitor"),
        ("/spectra/nope", 404, "monitor_not_found"),
    ],
)
def test_field_and_spectra_errors(results, url, status, code):
    response = results.get(f"/api/results/{RESULT_ID}{url}")
    assert response.status_code == status
    assert response.json()["code"] == code


def test_a_bad_quantity_is_422(results):
    response = results.get(f"/api/results/{RESULT_ID}/fields/field?quantity=power")
    assert response.status_code == 422


def test_spectra_are_the_stored_complex_values(results, npz):
    response = results.get(f"/api/results/{RESULT_ID}/spectra/out")
    assert response.status_code == 200
    body = response.json()
    assert body["monitor"] == "out"
    assert body["wavelengths_um"] == [1.5, 1.55, 1.6]
    assert list(body["components"]) == ["Hz"]
    stored = npz["m2.Hz"][0, 0, :]
    assert body["components"]["Hz"]["re"] == pytest.approx(stored.real.tolist(), rel=1e-6)
    assert body["components"]["Hz"]["im"] == pytest.approx(stored.imag.tolist(), rel=1e-6)


@pytest.mark.parametrize(
    "result_id",
    [
        "nonsense",
        f"{SIM_ID}~20200101T000000Z",
        f"{SIM_ID}~..%2F..%2Fsecret",
        f"000000000000~{recorded_folder().name}",
    ],
)
def test_unknown_results_are_404(results, result_id):
    response = results.get(f"/api/results/{result_id}")
    assert response.status_code == 404
    # A decoded "/" makes the path miss the route: the API's own 404, still no file read.
    assert response.json()["code"] in ("result_not_found", "not_found")
