"""Preview, estimate and warnings of a Simulation (plan-u1 §4, §13.2), and the εr slice."""

import numpy as np
import pytest

import etalon as et
from etalon.grid.materials import permittivity_on_nodes
from etalon.grid.yee import build_yee_grid
from etalon.studio.binary import unpack
from etalon.studio.preview import (
    build_estimate,
    build_preview,
    build_warnings,
    memory_bytes,
    run_backend,
    solver_grid,
)
from etalon.studio.throughput import ThroughputStore
from etalon.studio.workspace import simulation_id
from tests.studio.conftest import write_script

SI = et.Medium(n=3.476, name="Si")
SIO2 = et.Medium(n=1.444, name="SiO2")


def source(x=0.0, y=0.0, component="Hz", wavelength=1.55, bandwidth=0.3):
    return et.PointSource(
        center=(x, y, 0.0),
        component=component,
        pulse=et.GaussianPulse(wavelength=wavelength, bandwidth=bandwidth),
        name="src",
    )


def simulation(**changes):
    base = {
        "size": (4.0, 2.0, 0.0),
        "medium": SIO2,
        "structures": [
            et.Box(size=(8.0, 0.5, 0.0), medium=SI, name="strip"),
            et.Box(center=(1.0, 0.0, 0.0), size=(0.2, 0.2, 0.0), medium=SIO2),
        ],
        "grid": et.UniformGrid(dl=0.02),
        "boundary": et.PML(layers=28),
        "sources": [source(-1.5)],
        "monitors": [
            et.DFTMonitor(name="field", size=(3.8, 1.8, 0.0), wavelengths=[1.5, 1.6]),
            et.DFTMonitor(name="end", center=(1.5, 0.0, 0.0), wavelengths=[1.55]),
            et.DFTMonitor(
                name="cut", center=(0.5, 0.0, 0.0), size=(0.0, 1.0, 0.0), wavelengths=[1.55]
            ),
        ],
        "run_time": 100e-15,
    }
    return et.Simulation(**{**base, **changes})


def codes(sim):
    grid = solver_grid(sim)
    memory = None if grid is None else memory_bytes(sim, grid)
    return [w.root.code for w in build_warnings(sim, grid, memory)]


def test_preview_lists_every_object_with_its_id():
    sim = simulation()
    preview = build_preview(sim, solver_grid(sim))
    assert preview.is_2d and preview.plane_z == 0.0
    assert preview.background.name == "SiO2"
    # The second box reuses the background's medium: media lists structures' media once each.
    assert [(m.id, m.name, m.n) for m in preview.media] == [
        ("medium:0", "Si", 3.476),
        ("medium:1", "SiO2", 1.444),
    ]
    assert [s.medium_id for s in preview.structures] == ["medium:0", "medium:1"]
    assert [s.id for s in preview.structures] == ["structure:0", "structure:1"]
    assert preview.sources[0].id == "source:0"
    assert preview.sources[0].wavelength_um == 1.55
    assert {m.id: m.geometry for m in preview.monitors} == {
        "monitor:field": "plane",
        "monitor:end": "point",
        "monitor:cut": "line",
    }
    assert preview.monitors[0].components == ["Ex", "Ey", "Hz"]
    assert preview.pml.thickness == pytest.approx((0.56, 0.56, 0.0))
    grid = preview.grid
    assert grid is not None
    assert (grid.nx, grid.ny, grid.region_cells) == (256, 156, (200, 100))
    assert grid.steps == build_yee_grid(sim).n_steps(sim.run_time)


def test_a_clean_simulation_has_no_warnings():
    assert codes(simulation()) == []


def test_mesh_coarse_names_the_densest_medium_and_shortest_wavelength():
    sim = simulation(grid=et.UniformGrid(dl=0.025))
    grid = solver_grid(sim)
    (warning,) = [w.root for w in build_warnings(sim, grid, None) if w.root.code == "mesh_coarse"]
    assert warning.object_id == "grid"
    assert warning.params.medium == "Si"
    assert warning.params.wavelength_um == pytest.approx(1.40)  # 1.55 - 0.3 / 2
    assert warning.params.cells_per_wavelength == pytest.approx(1.40 / (3.476 * 0.025))
    assert warning.params.minimum == 20


def test_pml_thin_compares_with_half_a_wavelength_in_the_background():
    sim = simulation(boundary=et.PML(layers=12))
    (warning,) = [w.root for w in build_warnings(sim, solver_grid(sim), None)]
    assert warning.code == "pml_thin"
    assert warning.object_id == "boundary"
    assert warning.params.thickness_um == pytest.approx(0.24)
    assert warning.params.half_wavelength_um == pytest.approx(1.55 / 1.444 / 2)


@pytest.mark.parametrize(("x", "cells"), [(-1.99, 0), (-1.97, 1), (-1.95, 2)])
def test_near_pml_counts_whole_cells(x, cells):
    sim = simulation(sources=[source(x)])
    found = [w.root for w in build_warnings(sim, solver_grid(sim), None)]
    assert [(w.code, w.object_id, w.params.cells) for w in found] == [
        ("near_pml", "source:0", cells)
    ]


def test_a_monitor_reaching_the_pml_is_near_it():
    monitors = [et.DFTMonitor(name="all", size=(4.0, 2.0, 0.0), wavelengths=[1.55])]
    sim = simulation(monitors=monitors)
    found = [w.root for w in build_warnings(sim, solver_grid(sim), None)]
    assert [(w.code, w.object_id, w.params.cells) for w in found] == [
        ("near_pml", "monitor:all", 0)
    ]


def test_memory_large_above_4_gb():
    sim = simulation(size=(120.0, 120.0, 0.0), grid=et.UniformGrid(dl=0.002), monitors=[])
    memory = memory_bytes(sim, solver_grid(sim))
    assert memory > 4e9
    assert "memory_large" in codes(sim)


def test_3d_is_unsupported_with_no_grid_and_no_estimate():
    sim = simulation(size=(4.0, 2.0, 1.0))
    assert solver_grid(sim) is None
    preview = build_preview(sim, None)
    assert not preview.is_2d and preview.grid is None
    assert preview.pml.thickness == pytest.approx((0.56, 0.56, 0.56))
    (warning,) = [w.root for w in build_warnings(sim, None, None)]
    assert (warning.code, warning.severity, warning.params.feature) == (
        "unsupported",
        "error",
        "3d",
    )
    assert warning.params.milestone == "M1"


def test_a_tm_source_is_unsupported_and_named():
    sim = simulation(sources=[source(-1.5, component="Ez")])
    found = [w.root for w in build_warnings(sim, solver_grid(sim), None)]
    assert [(w.code, w.object_id, w.params.feature) for w in found] == [
        ("unsupported", "source:0", "tm")
    ]


def test_memory_matches_the_solver_summary():
    sim = simulation()
    grid = solver_grid(sim)
    fields_mb, monitors_mb = (
        float(part.split()[0])
        for part in sim.summary().splitlines()[-1].removeprefix("memory").split("+")
    )
    assert memory_bytes(sim, grid) / 1e6 == pytest.approx(fields_mb + monitors_mb, rel=2e-3)


@pytest.mark.parametrize(
    ("setting", "script", "gpu", "expected"),
    [
        ("cpu", "cuda", True, "cpu"),
        ("cuda:1", "numpy", False, "cuda:1"),
        ("auto", "numpy", True, "cpu"),
        ("auto", "cuda", False, "cuda:0"),
        ("auto", "auto", True, "cuda:0"),
        ("auto", "auto", False, "cpu"),
    ],
)
def test_run_backend(setting, script, gpu, expected):
    assert run_backend(setting, script, gpu) == expected


def test_estimate_uses_the_most_recent_throughput(tmp_path):
    sim = simulation()
    grid = solver_grid(sim)
    store = ThroughputStore(tmp_path)
    unknown = build_estimate(sim, grid, store, "cpu")
    assert (unknown.basis, unknown.seconds, unknown.cells_per_s) == ("unknown", None, None)
    store.record("calibration", "cpu", "CPU", 1e7)
    calibrated = build_estimate(sim, grid, store, "cpu")
    assert calibrated.basis == "calibration"
    assert calibrated.seconds == pytest.approx(grid.n_cells * calibrated.steps / 1e7)
    store.record("measured", "cpu", "CPU", 2e7)
    assert build_estimate(sim, grid, ThroughputStore(tmp_path), "cpu").basis == "measured"
    assert build_estimate(sim, grid, store, "cuda:0").basis == "unknown"


# The εr slice ---------------------------------------------------------------------------
SLICE_SCRIPT = """\
import etalon as et

sim = et.Simulation(
    size=(2.0, 1.0, 0.0),
    medium=et.Medium(n=1.444),
    structures=[et.Box(center=(0.3, 0.1, 0.0), size=(3.0, 0.4, 0.0), medium=et.Medium(n=3.476))],
    grid=et.UniformGrid(dl=0.05),
    sources=[et.PointSource(center=(-0.5, 0.0, 0.0), component="Hz",
                            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.3))],
    run_time=20e-15,
)
sim.run()
"""


@pytest.mark.parametrize("component", ["Ex", "Ey"])
def test_permittivity_slice_equals_the_solvers_own(client, workspace, component):
    write_script(workspace, "slice.py", SLICE_SCRIPT)
    sim_id = simulation_id("slice.py")
    response = client.get(f"/api/simulations/{sim_id}/permittivity?component={component}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    header, data = unpack(response.content)
    namespace: dict[str, object] = {}
    exec(SLICE_SCRIPT.replace("sim.run()", ""), namespace)
    sim = namespace["sim"]
    grid = build_yee_grid(sim)
    expected = permittivity_on_nodes(sim, grid)[component].astype(np.float32)
    np.testing.assert_array_equal(data, expected)
    x, y = grid.coords(component)
    assert header["kind"] == "permittivity"
    assert header["shape"] == list(expected.shape)
    assert header["extent"] == pytest.approx([x[0], x[-1], y[0], y[-1]])
    assert header["pml_cells"] == 12
    assert header["component"] == component
    assert (header["min"], header["max"]) == pytest.approx((1.444**2, 3.476**2), rel=1e-6)


def test_permittivity_of_a_3d_script_is_409(client, workspace):
    write_script(
        workspace, "slab.py", SLICE_SCRIPT.replace("size=(2.0, 1.0, 0.0)", "size=(2, 1, 1)")
    )
    response = client.get(f"/api/simulations/{simulation_id('slab.py')}/permittivity")
    assert response.status_code == 409
    assert response.json()["code"] == "unsupported"
    spec = client.get(f"/api/simulations/{simulation_id('slab.py')}/spec").json()
    assert spec["preview"]["grid"] is None and spec["estimate"] is None
    assert [w["code"] for w in spec["warnings"]] == ["unsupported"]
