"""Yee grid and materials (plan-m0 U3, U4)."""

import math

import numpy as np
import pytest

import etalon as et
from etalon.grid.materials import permittivity_on_nodes
from etalon.grid.yee import build_yee_grid, cells_along, courant_time_step
from tests.sims import small_sim


def test_cells_along_ignores_float_noise():
    assert 0.56 / 0.01 > 56  # the float noise this guards against
    assert cells_along(0.56, 0.01) == 56
    assert cells_along(1.0, 0.3) == 4  # never coarser than asked: Δ = 0.25 ≤ 0.3


def test_grid_counts_spacing_and_pml_outside_region():
    grid = build_yee_grid(small_sim(size=(8.0, 4.0, 0.0), boundary=et.PML(layers=12)))
    assert (grid.nx, grid.ny) == (160 + 24, 80 + 24)
    assert grid.region_cells == (160, 80)
    assert grid.dx == pytest.approx(0.05) and grid.dy == pytest.approx(0.05)
    assert grid.x_min == pytest.approx(-4.0 - 12 * 0.05)
    assert grid.y_min == pytest.approx(-2.0 - 12 * 0.05)
    x_ey, _ = grid.coords("Ey")  # integer nodes along x: node L is the region's left edge
    assert x_ey[12] == pytest.approx(-4.0) and x_ey[-13] == pytest.approx(4.0)


def test_non_multiple_size_keeps_edges_exact():
    grid = build_yee_grid(small_sim(size=(1.0, 1.0, 0.0), grid=et.UniformGrid(dl=0.3)))
    assert grid.region_cells == (4, 4)
    assert grid.dx == pytest.approx(0.25)


def test_component_shapes_and_coordinates():
    grid = build_yee_grid(small_sim())
    nx, ny = grid.nx, grid.ny
    assert grid.shape("Hz") == (nx, ny)
    assert grid.shape("Ex") == (nx, ny + 1)
    assert grid.shape("Ey") == (nx + 1, ny)
    x_hz, y_hz = grid.coords("Hz")
    x_ex, y_ex = grid.coords("Ex")
    x_ey, y_ey = grid.coords("Ey")
    assert x_hz[0] == pytest.approx(grid.x_min + 0.5 * grid.dx)
    assert y_hz[0] == pytest.approx(grid.y_min + 0.5 * grid.dy)
    np.testing.assert_array_equal(x_ex, x_hz)
    np.testing.assert_array_equal(y_ey, y_hz)
    assert x_ey[0] == grid.x_min and y_ex[0] == grid.y_min
    assert x_ey.size == nx + 1 and y_ex.size == ny + 1


def test_time_step_is_courant_fraction_of_limit():
    sim = small_sim(size=(2.0, 1.2, 0.0), grid=et.UniformGrid(dl=0.05), courant=0.7)
    grid = build_yee_grid(sim)
    limit = 1.0 / (et.C_0 * math.sqrt(1 / grid.dx**2 + 1 / grid.dy**2))
    assert grid.dt == pytest.approx(0.7 * limit, rel=1e-15)
    assert courant_time_step(1.0, 0.05, 0.05) == pytest.approx(0.05 / (et.C_0 * math.sqrt(2)))
    assert grid.n_steps(10 * grid.dt) == 10
    assert grid.n_steps(10.5 * grid.dt) == 11


def test_summary_reports_cost():
    text = small_sim().summary()
    assert "56 x 46 cells = 40 x 30 region + 8-cell CPML" in text
    assert "steps" in text and "MB fields" in text
    text.encode("ascii")  # printable on any console encoding


def test_3d_is_refused_with_the_milestone():
    sim = small_sim(size=(2.0, 1.5, 1.0))
    with pytest.raises(NotImplementedError, match="M1"):
        sim.summary()


def test_background_permittivity():
    sim = small_sim(medium=et.Medium(n=1.5))
    eps = permittivity_on_nodes(sim, build_yee_grid(sim))
    assert set(eps) == {"Ex", "Ey"}
    assert np.all(eps["Ex"] == 2.25) and np.all(eps["Ey"] == 2.25)


def test_box_staircase_faces_inclusive_later_wins():
    si = et.Medium(n=3.5)
    sin = et.Medium(n=2.0)
    boxes = [
        et.Box(center=(0.0, 0.0, 0.0), size=(0.5, 0.4, 0.22), medium=si),
        et.Box(center=(0.2, 0.0, 0.0), size=(0.2, 0.2, 0.22), medium=sin),
    ]
    sim = small_sim(structures=boxes)
    grid = build_yee_grid(sim)
    eps = permittivity_on_nodes(sim, grid)
    x, y = grid.coords("Ex")  # Ex: half nodes in x, integer nodes in y
    x_nodes, y_nodes = np.meshgrid(x, y, indexing="ij")
    in_si = (np.abs(x_nodes) <= 0.25 + 1e-9) & (np.abs(y_nodes) <= 0.2 + 1e-9)
    in_sin = (np.abs(x_nodes - 0.2) <= 0.1 + 1e-9) & (np.abs(y_nodes) <= 0.1 + 1e-9)
    expected = np.where(in_sin, 4.0, np.where(in_si, 3.5**2, 1.0))
    np.testing.assert_array_equal(eps["Ex"], expected)
    # y = ±0.2 lies exactly on Ex nodes: the face rows must be inside
    j_face = int(np.argmin(np.abs(y - 0.2)))
    assert abs(y[j_face] - 0.2) < 1e-12
    assert eps["Ex"][np.argmin(np.abs(x)), j_face] == pytest.approx(3.5**2)


def test_2d_box_inclusion_by_z_extent():
    si = et.Medium(n=3.5)
    above = et.Box(center=(0.0, 0.0, 0.5), size=(1.0, 1.0, 0.2), medium=si)
    flat = et.Box(center=(0.0, 0.0, 0.0), size=(1.0, 1.0, 0.0), medium=si)
    for box, expected_max in ((above, 1.0), (flat, 3.5**2)):
        sim = small_sim(structures=[box])
        eps = permittivity_on_nodes(sim, build_yee_grid(sim))
        assert eps["Ey"].max() == pytest.approx(expected_max)
