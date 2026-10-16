"""Device layouts from bench/config.yaml: polygons, region, ports and source plane.

Both codes build their geometry from these polygons, so a curved edge (arc, S-bend) is
the same vertex list in Meep (``mp.Prism``) and in etalon (``PolySlab``): like for like,
whatever each code then does for subpixel smoothing. Curves are sampled so that no
polygon edge strays more than ``curve_tolerance`` from the true curve.

Coordinates are in µm in the xy plane. In 3D every polygon is a slab of the strip
thickness centred on z = 0; in 2D it is z-invariant. Port numbering follows
mvp-spec §5; port 1 is the driven port and every source launches along +x.
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from bench.config import (
    MMI,
    BenchConfig,
    Bend,
    DirectionalCoupler,
    Point2D,
    Ports,
    Ring,
    Straight,
    Strip,
    Tier,
)

EXTEND = 5.0
"""Waveguides run this far past the region edge, so they pass through any PML."""

Normal = Literal["+x", "-x", "+y", "-y"]
Material = Literal["core", "cladding"]


@dataclass(frozen=True)
class Polygon:
    """A closed polygon, counter-clockwise, first vertex not repeated at the end."""

    vertices: np.ndarray
    """Shape (N, 2), µm."""
    material: Material
    """core: Si in 3D, the tier's core_index in 2D. cladding: SiO2 (e.g. a ring's hole)."""


@dataclass(frozen=True)
class Port:
    """A mode plane across one strip."""

    name: str
    """"1", "2", ...: the index in S_ij."""
    label: str
    """What the port is for: "in", "out", "through", "drop", ..."""
    center: tuple[float, float]
    normal: Normal
    """Outward normal: the direction in which a wave leaves the device through this port."""

    @property
    def axis(self) -> Literal["x", "y"]:
        return "x" if self.normal[1] == "x" else "y"

    @property
    def sign(self) -> int:
        """+1 if the outward normal points along +axis, −1 otherwise."""
        return 1 if self.normal[0] == "+" else -1


@dataclass(frozen=True)
class Layout:
    """Everything geometric about one device."""

    device: str
    region_center: tuple[float, float]
    region_size: tuple[float, float]
    polygons: tuple[Polygon, ...]
    """In order: later polygons win where they overlap (both codes follow this rule)."""
    ports: tuple[Port, ...]
    """Port 1 first; empty for point2d."""
    source_center: tuple[float, float]
    """Mode source plane (or, for point2d, the Hz point source); launches along +x."""
    background: Literal["si", "sio2"] = "sio2"
    probes: tuple[tuple[float, float], ...] = ()
    """point2d only: the Hz probe positions."""

    @property
    def region_bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """((x_min, x_max), (y_min, y_max)) of the region, PML excluded."""
        (cx, cy), (sx, sy) = self.region_center, self.region_size
        return (cx - sx / 2, cx + sx / 2), (cy - sy / 2, cy + sy / 2)


def layout(cfg: BenchConfig, name: str) -> Layout:
    """The layout of device ``name``."""
    device = cfg.device(name)
    tol = cfg.curve_tolerance
    region = (device.region.center, device.region.size)
    if isinstance(device, Point2D):
        return Layout(
            device=name,
            region_center=region[0],
            region_size=region[1],
            polygons=(),
            ports=(),
            source_center=device.source,
            background=device.medium,
            probes=device.probes,
        )
    if isinstance(device, Straight):
        polygons, ports = _straight(device, cfg.strip, cfg.ports, region)
    elif isinstance(device, Bend):
        polygons, ports = _bend(device, cfg.strip, cfg.ports, region, tol)
    elif isinstance(device, DirectionalCoupler):
        polygons, ports = _dc(device, cfg.strip, cfg.ports, region, tol)
    elif isinstance(device, MMI):
        polygons, ports = _mmi(device, cfg.strip, cfg.ports, region)
    elif isinstance(device, Ring):
        polygons, ports = _ring(device, cfg.strip, cfg.ports, region, tol)
    else:  # pragma: no cover - config.Devices fixes the set
        raise ValueError(f"no layout for device {name!r}")
    first = ports[0]
    offset = cfg.ports.source_offset
    source = (first.center[0] - offset, first.center[1])  # port 1 faces −x: upstream is −x
    return Layout(
        device=name,
        region_center=region[0],
        region_size=region[1],
        polygons=tuple(polygons),
        ports=tuple(ports),
        source_center=source,
    )


def mode_plane(
    center: tuple[float, float], normal: Normal, ports: Ports, tier: Tier
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """(centre, size) of a port or source plane: ``ports.width`` across, ``ports.height`` tall."""
    height = ports.height if tier.dims == 3 else 0.0
    if normal[1] == "x":
        size = (0.0, ports.width, height)
    else:
        size = (ports.width, 0.0, height)
    return (center[0], center[1], 0.0), size


# ---------------------------------------------------------------- devices

Region = tuple[tuple[float, float], tuple[float, float]]


def _far(region: Region) -> tuple[float, float, float, float]:
    """x_lo, x_hi, y_lo, y_hi EXTEND µm outside the region."""
    (cx, cy), (sx, sy) = region
    return (
        cx - sx / 2 - EXTEND,
        cx + sx / 2 + EXTEND,
        cy - sy / 2 - EXTEND,
        cy + sy / 2 + EXTEND,
    )


def _straight(
    d: Straight, strip: Strip, ports: Ports, region: Region
) -> tuple[list[Polygon], list[Port]]:
    x_lo, x_hi, _, _ = _far(region)
    path = _Path().straight((x_lo, 0.0), (x_hi, 0.0))
    half = d.length / 2
    return [path.polygon(strip.width)], [
        Port("1", "in", (-half, 0.0), "-x"),
        Port("2", "out", (half, 0.0), "+x"),
    ]


def _bend(
    d: Bend, strip: Strip, ports: Ports, region: Region, tol: float
) -> tuple[list[Polygon], list[Port]]:
    """Input along y = 0 to (0, 0), quarter circle about (0, R), output along x = R upwards."""
    x_lo, _, _, y_hi = _far(region)
    r = d.radius
    path = _Path().straight((x_lo, 0.0), (0.0, 0.0))
    path.arc((0.0, r), r, -90.0, 0.0, tol, strip.width)
    path.straight((r, r), (r, y_hi))
    return [path.polygon(strip.width)], [
        Port("1", "in", (-ports.lead, 0.0), "-x"),
        Port("2", "out", (r, r + ports.lead), "+y"),
    ]


def _dc(
    d: DirectionalCoupler, strip: Strip, ports: Ports, region: Region, tol: float
) -> tuple[list[Polygon], list[Port]]:
    """Two arms, mirror images in y = 0: port pitch ``pitch``, gap ``gap`` along the coupler."""
    x_lo, x_hi, _, _ = _far(region)
    y_port = -d.pitch / 2
    y_coupled = -(d.gap + strip.width) / 2
    x1 = d.coupling_length / 2
    x0 = x1 + d.sbend_length
    path = _Path().straight((x_lo, y_port), (-x0, y_port))
    path.cosine_sbend((-x0, y_port), (-x1, y_coupled), tol, strip.width)
    path.straight((-x1, y_coupled), (x1, y_coupled))
    path.cosine_sbend((x1, y_coupled), (x0, y_port), tol, strip.width)
    path.straight((x0, y_port), (x_hi, y_port))
    bottom = path.polygon(strip.width)
    top = Polygon(_mirror_y(bottom.vertices), "core")
    xp = x0 + ports.lead
    return [bottom, top], [
        Port("1", "in", (-xp, y_port), "-x"),
        Port("2", "isolated", (-xp, -y_port), "-x"),
        Port("3", "through", (xp, y_port), "+x"),
        Port("4", "cross", (xp, -y_port), "+x"),
    ]


def _mmi(d: MMI, strip: Strip, ports: Ports, region: Region) -> tuple[list[Polygon], list[Port]]:
    """Centre-fed 1×2: input taper, rectangular body, two output tapers at y = ±offset."""
    x_lo, x_hi, _, _ = _far(region)
    w, tw, tl = strip.width / 2, d.taper_width / 2, d.taper_length
    half, body, o = d.length / 2, d.width / 2, d.output_offset
    if o + tw > body or o - tw <= 0.0:
        raise ValueError("MMI output tapers must lie inside the body and must not touch")
    # one simple polygon, counter-clockwise from the input's lower edge
    vertices = [
        (x_lo, -w),
        (-half - tl, -w),
        (-half, -tw),
        (-half, -body),
        (half, -body),
        (half, -o - tw),
        (half + tl, -o - w),
        (x_hi, -o - w),
        (x_hi, -o + w),
        (half + tl, -o + w),
        (half, -o + tw),
        (half, o - tw),
        (half + tl, o - w),
        (x_hi, o - w),
        (x_hi, o + w),
        (half + tl, o + w),
        (half, o + tw),
        (half, body),
        (-half, body),
        (-half, tw),
        (-half - tl, w),
        (x_lo, w),
    ]
    xp = half + tl + ports.lead
    return [Polygon(np.array(vertices, dtype=float), "core")], [
        Port("1", "in", (-xp, 0.0), "-x"),
        Port("2", "out +y", (xp, o), "+x"),
        Port("3", "out -y", (xp, -o), "+x"),
    ]


def _ring(
    d: Ring, strip: Strip, ports: Ports, region: Region, tol: float
) -> tuple[list[Polygon], list[Port]]:
    """Add-drop racetrack between two straight buses; the ring is Si outline minus SiO2 hole."""
    x_lo, x_hi, _, _ = _far(region)
    w = strip.width
    y_bus = d.radius + d.straight_y / 2 + w + d.gap
    outer = _racetrack(d.straight_x, d.straight_y, d.radius + w / 2, tol)
    inner = _racetrack(d.straight_x, d.straight_y, d.radius - w / 2, tol)
    bottom = _Path().straight((x_lo, -y_bus), (x_hi, -y_bus)).polygon(w)
    top = _Path().straight((x_lo, y_bus), (x_hi, y_bus)).polygon(w)
    # ports a lead beyond the racetrack's centreline extent, which keeps them on grid nodes
    xp = d.straight_x / 2 + d.radius + ports.lead
    return [bottom, top, Polygon(outer, "core"), Polygon(inner, "cladding")], [
        Port("1", "in", (-xp, -y_bus), "-x"),
        Port("2", "through", (xp, -y_bus), "+x"),
        Port("3", "drop", (-xp, y_bus), "-x"),
        Port("4", "add", (xp, y_bus), "+x"),
    ]


# ---------------------------------------------------------------- geometry helpers


class _Path:
    """A strip centreline built from segments; ``polygon(width)`` offsets it by ±width/2.

    Each sample carries its exact unit tangent, so the offset edges are exactly width/2
    from the centreline at every vertex, also at joints between segments.
    """

    def __init__(self) -> None:
        self.points: list[tuple[float, float]] = []
        self.tangents: list[tuple[float, float]] = []

    def _add(self, points: np.ndarray, tangents: np.ndarray) -> "_Path":
        start = 0
        if self.points and np.allclose(self.points[-1], points[0], atol=1e-12):
            start = 1  # the joint is shared with the previous segment
        self.points.extend(map(tuple, points[start:]))
        self.tangents.extend(map(tuple, tangents[start:]))
        return self

    def straight(self, p0: tuple[float, float], p1: tuple[float, float]) -> "_Path":
        a, b = np.asarray(p0, float), np.asarray(p1, float)
        t = (b - a) / np.linalg.norm(b - a)
        return self._add(np.array([a, b]), np.array([t, t]))

    def arc(
        self,
        center: tuple[float, float],
        radius: float,
        start_deg: float,
        end_deg: float,
        tol: float,
        width: float,
    ) -> "_Path":
        """Circular arc; sampled finely enough for the OUTER edge (radius + width/2)."""
        theta = arc_angles(radius + width / 2, start_deg, end_deg, tol)
        c = np.asarray(center, float)
        points = c + radius * np.column_stack([np.cos(theta), np.sin(theta)])
        turn = 1.0 if end_deg > start_deg else -1.0
        tangents = turn * np.column_stack([-np.sin(theta), np.cos(theta)])
        return self._add(points, tangents)

    def cosine_sbend(
        self, p0: tuple[float, float], p1: tuple[float, float], tol: float, width: float
    ) -> "_Path":
        """y = y0 + (y1 − y0)(1 − cos πs)/2, s = (x − x0)/(x1 − x0): zero slope at both ends."""
        (x0, y0), (x1, y1) = p0, p1
        length, rise = x1 - x0, y1 - y0
        # smallest radius of curvature, at the ends: R = 2L²/(π²|Δy|); sample for the outer edge
        r_min = 2 * length**2 / (math.pi**2 * abs(rise)) - width / 2
        step = math.sqrt(8 * r_min * tol)
        s = np.linspace(0.0, 1.0, math.ceil(abs(length) / step) + 1)
        x = x0 + length * s
        y = y0 + rise * (1 - np.cos(math.pi * s)) / 2
        slope = rise * math.pi * np.sin(math.pi * s) / (2 * length)
        tangents = np.column_stack([np.ones_like(s), slope]) * math.copysign(1.0, length)
        tangents /= np.linalg.norm(tangents, axis=1, keepdims=True)
        return self._add(np.column_stack([x, y]), tangents)

    def polygon(self, width: float) -> Polygon:
        p, t = np.array(self.points), np.array(self.tangents)
        left = p + 0.5 * width * np.column_stack([-t[:, 1], t[:, 0]])
        right = p - 0.5 * width * np.column_stack([-t[:, 1], t[:, 0]])
        return Polygon(np.concatenate([right, left[::-1]]), "core")


def arc_angles(radius: float, start_deg: float, end_deg: float, tol: float) -> np.ndarray:
    """Angles (rad) along an arc whose chords stay within ``tol`` of the circle.

    A chord subtending Δθ deviates from its arc by the sagitta r(1 − cos Δθ/2) ≤ tol.
    """
    max_step = 2.0 * math.acos(1.0 - tol / radius)
    sweep = math.radians(end_deg - start_deg)
    n = max(1, math.ceil(abs(sweep) / max_step))
    return np.linspace(math.radians(start_deg), math.radians(end_deg), n + 1)


def _racetrack(sx: float, sy: float, r: float, tol: float) -> np.ndarray:
    """Counter-clockwise racetrack: straights sx (along x) and sy (along y), corner radius r."""
    pieces = []
    for cx, cy, a0 in ((sx / 2, -sy / 2, -90.0), (sx / 2, sy / 2, 0.0)):
        theta = arc_angles(r, a0, a0 + 90.0, tol)
        pieces.append(np.column_stack([cx + r * np.cos(theta), cy + r * np.sin(theta)]))
    for cx, cy, a0 in ((-sx / 2, sy / 2, 90.0), (-sx / 2, -sy / 2, 180.0)):
        theta = arc_angles(r, a0, a0 + 90.0, tol)
        pieces.append(np.column_stack([cx + r * np.cos(theta), cy + r * np.sin(theta)]))
    # consecutive arcs are joined by the straights; the closing straight is implicit
    return np.concatenate(pieces)


def _mirror_y(vertices: np.ndarray) -> np.ndarray:
    """Mirror in y = 0, reversing the order so the polygon stays counter-clockwise."""
    mirrored = vertices * np.array([1.0, -1.0])
    return np.ascontiguousarray(mirrored[::-1])
