"""B2: device geometry — polygons, widths, gaps, ports and source planes."""

import itertools
import math

import numpy as np
import pytest
from matplotlib.path import Path as MplPath

from bench.config import BenchConfig, load_config
from bench.devices import Layout, arc_angles, layout, mode_plane

DEVICES = ("straight", "bend", "dc", "mmi", "ring")


@pytest.fixture(scope="module")
def cfg() -> BenchConfig:
    return load_config()


@pytest.fixture(scope="module")
def layouts(cfg) -> dict[str, Layout]:
    return {name: layout(cfg, name) for name in (*DEVICES, "point2d")}


def edges(v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return v, np.roll(v, -1, axis=0)


def signed_area(v: np.ndarray) -> float:
    a, b = edges(v)
    return 0.5 * float(np.sum(a[:, 0] * b[:, 1] - b[:, 0] * a[:, 1]))


def self_intersects(v: np.ndarray) -> bool:
    """True if two non-adjacent edges cross (vectorised segment test)."""
    a, b = edges(v)
    n = len(v)

    def orient(p, q, r):
        return np.sign(
            (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1])
            - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
        )

    p1, p2 = a[:, None, :], b[:, None, :]
    q1, q2 = a[None, :, :], b[None, :, :]
    cross = (orient(p1, p2, q1) * orient(p1, p2, q2) < 0) & (
        orient(q1, q2, p1) * orient(q1, q2, p2) < 0
    )
    i, j = np.indices((n, n))
    adjacent = (np.abs(i - j) <= 1) | (np.abs(i - j) == n - 1)
    return bool(np.any(cross & ~adjacent))


def crossings(v: np.ndarray, axis: int, value: float) -> np.ndarray:
    """Sorted coordinates (along the other axis) where the polygon boundary crosses axis = value."""
    a, b = edges(v)
    other = 1 - axis
    lo, hi = np.minimum(a[:, axis], b[:, axis]), np.maximum(a[:, axis], b[:, axis])
    hit = (lo <= value) & (value < hi)
    t = (value - a[hit, axis]) / (b[hit, axis] - a[hit, axis])
    return np.sort(a[hit, other] + t * (b[hit, other] - a[hit, other]))


def core_intervals(lay: Layout, axis: int, value: float) -> list[tuple[float, float]]:
    """Intervals along the other axis that are core material, applying 'later wins'."""
    coords = sorted({c for p in lay.polygons for c in crossings(p.vertices, axis, value)})
    out = []
    for lo, hi in itertools.pairwise(coords):
        mid = 0.5 * (lo + hi)
        point = (value, mid) if axis == 0 else (mid, value)
        material = "cladding"
        for poly in lay.polygons:
            if MplPath(poly.vertices).contains_point(point):
                material = poly.material
        if material == "core":
            if out and abs(out[-1][1] - lo) < 1e-12:
                out[-1] = (out[-1][0], hi)
            else:
                out.append((lo, hi))
    return out


@pytest.mark.parametrize("name", DEVICES)
def test_polygons_are_simple_and_counter_clockwise(layouts, name):
    for poly in layouts[name].polygons:
        v = poly.vertices
        assert v.ndim == 2 and v.shape[1] == 2 and np.all(np.isfinite(v))
        assert not np.allclose(v[0], v[-1]), "closing vertex must not be repeated"
        assert signed_area(v) > 0
        assert not self_intersects(v)


def test_arc_sampling_respects_tolerance():
    for r in (0.5, 5.0, 10.25):
        theta = arc_angles(r, -90.0, 0.0, 1e-4)
        sagitta = r * (1 - math.cos(0.5 * (theta[1] - theta[0])))
        assert sagitta <= 1e-4 + 1e-15
        assert theta[0] == pytest.approx(-math.pi / 2) and theta[-1] == pytest.approx(0.0)


def test_straight(layouts):
    lay = layouts["straight"]
    assert core_intervals(lay, 0, 0.0) == [(-0.25, 0.25)]
    assert lay.ports[1].center[0] - lay.ports[0].center[0] == 10.0


def test_bend_edges_on_circles(layouts, cfg):
    lay, r, w = layouts["bend"], cfg.devices.bend.radius, cfg.strip.width
    v = lay.polygons[0].vertices
    on_arc = (v[:, 0] > 1e-9) & (v[:, 1] < r - 1e-9)
    radius = np.hypot(v[on_arc, 0], v[on_arc, 1] - r)
    assert np.all(np.isclose(radius, r - w / 2) | np.isclose(radius, r + w / 2))
    # chord midpoints stay within the curve tolerance of the outer and inner circles
    a, b = edges(v)
    mid = 0.5 * (a + b)
    arc_mid = mid[(mid[:, 0] > 0.01) & (mid[:, 1] < r - 0.01)]
    deviation = np.minimum(
        np.abs(np.hypot(arc_mid[:, 0], arc_mid[:, 1] - r) - (r + w / 2)),
        np.abs(np.hypot(arc_mid[:, 0], arc_mid[:, 1] - r) - (r - w / 2)),
    )
    assert deviation.max() <= cfg.curve_tolerance
    assert core_intervals(lay, 1, r + 0.5) == [(r - w / 2, r + w / 2)]


def test_dc_gap_and_pitch(layouts, cfg):
    lay, d, w = layouts["dc"], cfg.devices.dc, cfg.strip.width
    (b_lo, b_hi), (t_lo, t_hi) = core_intervals(lay, 0, 0.0)
    assert t_lo - b_hi == pytest.approx(d.gap, abs=1e-12)
    assert b_hi - b_lo == pytest.approx(w) and t_hi - t_lo == pytest.approx(w)
    x_port = lay.ports[0].center[0]
    (b_lo, b_hi), (t_lo, t_hi) = core_intervals(lay, 0, x_port)
    assert 0.5 * (t_lo + t_hi) - 0.5 * (b_lo + b_hi) == pytest.approx(d.pitch)


def test_dc_sbend_width(layouts, cfg):
    """Every S-bend vertex is exactly w/2 from the analytic cosine centreline."""
    d, w = cfg.devices.dc, cfg.strip.width
    x0, x1 = d.coupling_length / 2, d.coupling_length / 2 + d.sbend_length
    y0, y1 = -(d.gap + w) / 2, -d.pitch / 2
    s = np.linspace(0, 1, 200_001)
    curve = np.column_stack([x0 + (x1 - x0) * s, y0 + (y1 - y0) * (1 - np.cos(np.pi * s)) / 2])
    v = layouts["dc"].polygons[0].vertices
    in_bend = v[(v[:, 0] > x0 + 1e-6) & (v[:, 0] < x1 - 1e-6)]
    dist = np.array([np.min(np.hypot(*(curve - p).T)) for p in in_bend[::7]])
    assert np.allclose(dist, w / 2, atol=2e-5)


def test_mmi(layouts, cfg):
    lay, m = layouts["mmi"], cfg.devices.mmi
    assert core_intervals(lay, 0, 0.0) == [(-m.width / 2, m.width / 2)]
    out = core_intervals(lay, 0, lay.ports[1].center[0])
    assert [0.5 * (lo + hi) for lo, hi in out] == pytest.approx([-1.5, 1.5])
    assert [hi - lo for lo, hi in out] == pytest.approx([0.5, 0.5])
    assert core_intervals(lay, 0, lay.ports[0].center[0]) == [(-0.25, 0.25)]


def test_ring_gaps_and_radii(layouts, cfg):
    lay, r, w = layouts["ring"], cfg.devices.ring, cfg.strip.width
    bus_lo, ring_lo, ring_hi, bus_hi = core_intervals(lay, 0, 0.0)
    assert ring_lo[0] - bus_lo[1] == pytest.approx(r.gap, abs=1e-12)
    assert bus_hi[0] - ring_hi[1] == pytest.approx(r.gap, abs=1e-12)
    assert ring_lo[1] - ring_lo[0] == pytest.approx(w)
    outer, inner = lay.polygons[2].vertices, lay.polygons[3].vertices
    for v, radius in ((outer, r.radius + w / 2), (inner, r.radius - w / 2)):
        cx = np.sign(v[:, 0]) * r.straight_x / 2
        cy = np.sign(v[:, 1]) * r.straight_y / 2
        assert np.allclose(np.hypot(v[:, 0] - cx, v[:, 1] - cy), radius)
    # the side of the racetrack: ring width w at y = 0
    assert core_intervals(lay, 1, 0.0) == [
        pytest.approx(
            (-(r.straight_x / 2 + r.radius + w / 2), -(r.straight_x / 2 + r.radius - w / 2))
        ),
        pytest.approx((r.straight_x / 2 + r.radius - w / 2, r.straight_x / 2 + r.radius + w / 2)),
    ]


@pytest.mark.parametrize("name", DEVICES)
def test_ports_hold_one_centred_strip_inside_the_region(layouts, cfg, name):
    lay = layouts[name]
    (x_lo, x_hi), (y_lo, y_hi) = lay.region_bounds
    half = cfg.ports.width / 2
    for port in lay.ports:
        axis = 0 if port.axis == "x" else 1
        along, across = port.center[axis], port.center[1 - axis]
        strips = [
            (lo, hi)
            for lo, hi in core_intervals(lay, axis, along)
            if hi > across - half and lo < across + half
        ]
        assert len(strips) == 1, f"port {port.name} plane must hold exactly one strip"
        (lo, hi) = strips[0]
        assert lo > across - half and hi < across + half
        assert 0.5 * (lo + hi) == pytest.approx(across, abs=1e-9)
        assert hi - lo == pytest.approx(cfg.strip.width)
        # plane inside the region, PML excluded
        bounds = ((x_lo, x_hi), (y_lo, y_hi))
        assert bounds[axis][0] < along < bounds[axis][1]
        assert bounds[1 - axis][0] <= across - half and across + half <= bounds[1 - axis][1]


@pytest.mark.parametrize("name", DEVICES)
def test_source_upstream_of_port_1_inside_the_region(layouts, cfg, name):
    lay = layouts[name]
    first = lay.ports[0]
    assert first.normal == "-x"
    assert lay.source_center == pytest.approx(
        (first.center[0] - cfg.ports.source_offset, first.center[1])
    )
    (x_lo, _), _ = lay.region_bounds
    assert lay.source_center[0] > x_lo


@pytest.mark.parametrize("name", DEVICES)
def test_strips_run_through_the_pml(layouts, cfg, name):
    """Beyond every port, the strip continues to the outer edge of the thickest PML."""
    lay = layouts[name]
    pml = max(t.pml for t in cfg.tiers.values())
    (x_lo, x_hi), (y_lo, y_hi) = lay.region_bounds
    edge = {"-x": x_lo - pml, "+x": x_hi + pml, "+y": y_hi + pml, "-y": y_lo - pml}
    paths = [MplPath(p.vertices) for p in lay.polygons if p.material == "core"]
    for port in lay.ports:
        axis = 0 if port.axis == "x" else 1
        end = edge[port.normal]
        for t in np.linspace(port.center[axis], end, 50):
            point = list(port.center)
            point[axis] = t
            assert any(path.contains_point(point) for path in paths)


def test_everything_sits_on_grid_nodes(layouts, cfg):
    """Port planes, source planes and region edges on nodes in every tier that runs a device."""
    for tier in cfg.tiers.values():
        for name in tier.devices:
            lay = layouts[name]
            points = [p.center for p in lay.ports] + [lay.source_center]
            offset = 0.5 if name == "point2d" else 0.0  # point2d: Hz nodes, half a cell off
            for point in points + list(lay.probes):
                cells = np.asarray(point) * tier.resolution - offset
                assert np.allclose(cells, np.round(cells), atol=1e-6), (name, point)


def test_mode_planes(cfg, layouts):
    port = layouts["bend"].ports[1]
    centre, size = mode_plane(port.center, port.normal, cfg.ports, cfg.tier("3d"))
    assert centre == (5.0, 6.0, 0.0) and size == (2.5, 0.0, 2.2)
    centre, size = mode_plane(port.center, port.normal, cfg.ports, cfg.tier("2d"))
    assert size == (2.5, 0.0, 0.0)
    port = layouts["straight"].ports[0]
    assert mode_plane(port.center, port.normal, cfg.ports, cfg.tier("3d"))[1] == (0.0, 2.5, 2.2)


def test_point2d(layouts, cfg):
    lay = layouts["point2d"]
    (p1, p2) = lay.probes
    assert p2[0] - p1[0] == pytest.approx(4.0) and p1[1] == p2[1] == lay.source_center[1]
    assert lay.source_center[0] < p1[0] and lay.polygons == () and lay.background == "sio2"
