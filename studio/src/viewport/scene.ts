/**
 * What the Setup viewport draws, as plain data (no React, no three): `buildScene` turns
 * the server's Preview (plan-u1 §13.2, µm) into boxes, markers and wireframes with their
 * display colours, plus the camera maths for framing them. Viewport3D turns this into
 * three.js objects; everything here is unit-tested without WebGL.
 */
import type { components } from "../api/schema";

export type Preview = components["schemas"]["Preview"];
type PreviewMonitor = components["schemas"]["PreviewMonitor"];
type PreviewSource = components["schemas"]["PreviewSource"];
type PreviewStructure = components["schemas"]["PreviewStructure"];

export type Vec3 = [number, number, number];
export type FieldComponent = PreviewSource["component"];

/** An axis-aligned box, µm. */
export interface SceneBox {
  center: Vec3;
  size: Vec3;
}

export interface Bounds {
  min: Vec3;
  max: Vec3;
}

/** The simulation region (PML excluded). It carries the Preview id of the grid. */
export interface SceneRegion extends SceneBox {
  id: "grid";
  /** Colour of the background medium on the index ramp, drawn translucent. */
  color: string;
  opacity: number;
}

export type PmlFace = "x-" | "x+" | "y-" | "y+" | "z-" | "z+";

/** One slab of the PML shell; all of them carry the Preview id of the boundary. */
export interface ScenePml extends SceneBox {
  id: "boundary";
  face: PmlFace;
}

export interface SceneStructure extends SceneBox {
  id: string;
  name: string | null;
  mediumId: string;
  /** Refractive index of its medium (NaN if the medium is missing from the Preview). */
  n: number;
  color: string;
  opacity: number;
  /** Cut to the simulation domain (region + PML) because it extends beyond it. */
  clipped: boolean;
  /**
   * 2D only: false when the simulated plane z = plane_z lies outside the box's z extent,
   * so the solver ignores it. Such a box is drawn where it is, as a ghost.
   */
  inPlane: boolean;
}

export interface SceneSource {
  id: string;
  name: string | null;
  position: Vec3;
  component: FieldComponent;
  /** Unit vector of the component's axis: Ex/Hx → x, Ey/Hy → y, Ez/Hz → z. */
  axis: Vec3;
  color: string;
}

/** How a monitor is drawn, from its number of non-zero display axes (0, 1, 2, 3). */
export type MonitorShape = "point" | "line" | "rect" | "box";

export interface SceneMonitor extends SceneBox {
  id: string;
  name: string;
  geometry: PreviewMonitor["geometry"];
  shape: MonitorShape;
  color: string;
}

export interface Scene {
  is2d: boolean;
  planeZ: number;
  /** Display thickness of the region slab along z (2D), or the region's own size_z (3D). */
  thickness: number;
  region: SceneRegion;
  pml: ScenePml[];
  structures: SceneStructure[];
  sources: SceneSource[];
  monitors: SceneMonitor[];
  /** Everything drawn. */
  bounds: Bounds;
  /** Largest side of `bounds`, µm. */
  extent: number;
  /** Radius of source and point-monitor markers, µm (a fixed fraction of `extent`). */
  markerRadius: number;
}

/** 2D: the region slab is this fraction of the larger in-plane size thick … */
export const THICKNESS_FRACTION = 0.04;
/** … but at least this many grid cells (dx), so it never reads as a sheet. */
export const THICKNESS_MIN_CELLS = 2;
/**
 * 2D: a box drawn at the display thickness and overlapping earlier ones (in-plane) is drawn
 * this fraction of the thickness taller per level of overlap, so the later box, which wins
 * in the solver (etalon/grid/materials.py: the last structure containing a node), shows its
 * top face and is picked first, with no z-fighting. Capped at STAGGER_MAX in total.
 */
export const STAGGER_STEP = 0.04;
export const STAGGER_MAX = 0.24;
/** 2D: monitors stand this fraction of the thickness above the tallest box, so they show. */
export const MONITOR_LIFT = 0.08;
export const MARKER_FRACTION = 0.012;
/** A selection smaller than this fraction of the scene is framed with some context. */
export const MIN_FRAME_FRACTION = 0.15;

// ---------------------------------------------------------------------------------------
// Colours

/**
 * Refractive index → display colour, a fixed ramp (the same in both themes), linear in n
 * and in sRGB between the stops; n below 1 is drawn as 1, n above 3 as 3:
 *
 * | n     | colour  | opacity | reads as                                                  |
 * | ----- | ------- | ------- | --------------------------------------------------------- |
 * | 1     | #3A414C | 0.25    | vacuum, air: the dark theme's rule colour, nearly clear   |
 * | 1.444 | #5E7A94 | 0.80    | silica: a cool grey-blue, see-through enough for a core   |
 * | (2.0) | #898575 | 0.87    | silicon nitride, interpolated: a neutral grey             |
 * | ≥ 3   | #D69A3C | 1       | silicon (3.476): a warm amber, close to the accent        |
 *
 * The amber is a little deeper than the accent (#E8B34A) so that the accent-ink selection
 * outline still shows on a silicon box.
 */
export const INDEX_RAMP: readonly { n: number; color: string; opacity: number }[] = [
  { n: 1, color: "#3A414C", opacity: 0.25 },
  { n: 1.444, color: "#5E7A94", opacity: 0.8 },
  { n: 3, color: "#D69A3C", opacity: 1 },
];

/** Opacity of the region slab, times the background medium's ramp opacity. */
export const REGION_OPACITY = 0.4;
/** Opacity factor of a 2D box outside the simulated plane (a ghost). */
export const GHOST_OPACITY = 0.35;

/** Okabe–Ito colours for markers, which read on both the amber and the grey-blue boxes. */
export const SOURCE_E_COLOR = "#0072B2"; // blue
export const SOURCE_H_COLOR = "#CC79A7"; // reddish purple
export const MONITOR_COLOR = "#009E73"; // bluish green

function hexToRgb(hex: string): Vec3 {
  const value = parseInt(hex.slice(1), 16);
  return [value >> 16, (value >> 8) & 0xff, value & 0xff];
}

function rgbToHex([r, g, b]: Vec3): string {
  const hex = (c: number) => Math.round(Math.min(255, Math.max(0, c))).toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`.toUpperCase();
}

/** The display colour and opacity of a medium of index n (INDEX_RAMP). */
export function indexColor(n: number): { color: string; opacity: number } {
  const first = INDEX_RAMP[0];
  const last = INDEX_RAMP[INDEX_RAMP.length - 1];
  if (!first || !last) throw new Error("empty INDEX_RAMP");
  if (!Number.isFinite(n) || n <= first.n) return { color: first.color, opacity: first.opacity };
  if (n >= last.n) return { color: last.color, opacity: last.opacity };
  for (let i = 1; i < INDEX_RAMP.length; i++) {
    const lo = INDEX_RAMP[i - 1];
    const hi = INDEX_RAMP[i];
    if (!lo || !hi || n > hi.n) continue;
    const t = (n - lo.n) / (hi.n - lo.n);
    const a = hexToRgb(lo.color);
    const b = hexToRgb(hi.color);
    return {
      color: rgbToHex([0, 1, 2].map((k) => (a[k] ?? 0) + t * ((b[k] ?? 0) - (a[k] ?? 0))) as Vec3),
      opacity: lo.opacity + t * (hi.opacity - lo.opacity),
    };
  }
  return { color: last.color, opacity: last.opacity };
}

/** Red minus blue of a #rrggbb colour: positive is warm, negative is cool. */
export function warmth(hex: string): number {
  const [r, , b] = hexToRgb(hex);
  return r - b;
}

// ---------------------------------------------------------------------------------------
// Boxes

function lo(box: SceneBox, axis: number): number {
  return (box.center[axis] ?? 0) - (box.size[axis] ?? 0) / 2;
}

function hi(box: SceneBox, axis: number): number {
  return (box.center[axis] ?? 0) + (box.size[axis] ?? 0) / 2;
}

export function boxBounds(box: SceneBox): Bounds {
  return { min: [lo(box, 0), lo(box, 1), lo(box, 2)], max: [hi(box, 0), hi(box, 1), hi(box, 2)] };
}

function boundsBox(bounds: Bounds): SceneBox {
  const center = [0, 1, 2].map((k) => ((bounds.min[k] ?? 0) + (bounds.max[k] ?? 0)) / 2) as Vec3;
  const size = [0, 1, 2].map((k) => (bounds.max[k] ?? 0) - (bounds.min[k] ?? 0)) as Vec3;
  return { center, size };
}

export function unionBounds(boxes: readonly Bounds[]): Bounds | null {
  if (boxes.length === 0) return null;
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (const b of boxes) {
    for (let k = 0; k < 3; k++) {
      min[k] = Math.min(min[k] ?? Infinity, b.min[k] ?? Infinity);
      max[k] = Math.max(max[k] ?? -Infinity, b.max[k] ?? -Infinity);
    }
  }
  return { min, max };
}

/**
 * The edges of a box as line-segment endpoints [x0, y0, z0, x1, y1, z1, …]: 12 for a box,
 * 4 for a rectangle (one zero side), 1 for a line, none for a point.
 */
export function boxEdgeSegments(box: SceneBox): number[] {
  const corner = (i: number): Vec3 =>
    [0, 1, 2].map((k) => (box.center[k] ?? 0) + (((i >> k) & 1) - 0.5) * (box.size[k] ?? 0)) as Vec3;
  const out: number[] = [];
  const seen = new Set<string>();
  for (let i = 0; i < 8; i++) {
    for (let k = 0; k < 3; k++) {
      const j = i | (1 << k);
      if (j === i || (box.size[k] ?? 0) === 0) continue;
      const a = corner(i);
      const b = corner(j);
      const key = [...a, ...b].join(",");
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(...a, ...b);
    }
  }
  return out;
}

function pointBounds(p: Vec3): Bounds {
  return { min: [...p], max: [...p] };
}

/** Whether two boxes overlap with positive area in the xy plane. */
function overlapsInPlane(a: SceneBox, b: SceneBox): boolean {
  return [0, 1].every((k) => Math.min(hi(a, k), hi(b, k)) - Math.max(lo(a, k), lo(b, k)) > 0);
}

/**
 * Cut `box` to `domain` along `axes` (only where the box has a size). A box entirely
 * outside the domain is returned as it is, so it is still drawn where the script put it.
 */
function clip(box: SceneBox, domain: Bounds, axes: readonly number[]): { box: SceneBox; clipped: boolean } {
  const center: Vec3 = [...box.center];
  const size: Vec3 = [...box.size];
  let clipped = false;
  for (const k of axes) {
    if ((box.size[k] ?? 0) <= 0) continue;
    const a = Math.max(lo(box, k), domain.min[k] ?? -Infinity);
    const b = Math.min(hi(box, k), domain.max[k] ?? Infinity);
    if (b <= a) return { box, clipped: false };
    if (a > lo(box, k) || b < hi(box, k)) clipped = true;
    center[k] = (a + b) / 2;
    size[k] = b - a;
  }
  return { box: { center, size }, clipped };
}

const AXIS: Record<FieldComponent, Vec3> = {
  Ex: [1, 0, 0],
  Ey: [0, 1, 0],
  Ez: [0, 0, 1],
  Hx: [1, 0, 0],
  Hy: [0, 1, 0],
  Hz: [0, 0, 1],
};

const SHAPES: readonly MonitorShape[] = ["point", "line", "rect", "box"];

// ---------------------------------------------------------------------------------------
// The scene

/** The 2D region slab's display thickness: max(0.04 × larger in-plane size, 2 dx). */
export function displayThickness(preview: Preview): number {
  const [sx, sy] = preview.region.size;
  const fromSize = THICKNESS_FRACTION * Math.max(sx, sy);
  const fromGrid = preview.grid ? THICKNESS_MIN_CELLS * preview.grid.dx : 0;
  return Math.max(fromSize, fromGrid);
}

function structureBoxes(
  preview: Preview,
  domain: Bounds,
  thickness: number,
): SceneStructure[] {
  const media = new Map(preview.media.map((m) => [m.id, m]));
  const planeZ = preview.plane_z;
  // Pass 1: in-plane clip and the z extent each box is drawn with.
  const drafts = preview.structures.map((s: PreviewStructure) => {
    const [, , cz] = s.center;
    const [, , sz] = s.size;
    const n = media.get(s.medium_id)?.n ?? Number.NaN;
    const ramp = indexColor(n);
    if (!preview.is_2d) {
      const { box, clipped } = clip({ center: [...s.center], size: [...s.size] }, domain, [0, 1, 2]);
      return { s, n, ramp, box, clipped, inPlane: true, slab: false };
    }
    const inPlane = Math.abs(planeZ - cz) <= sz / 2 + 1e-9;
    // The display thickness for a 0 or over-thick box in the plane, and for a sheet off it.
    const slab = (inPlane && (sz <= 0 || sz > thickness)) || (!inPlane && sz <= 0);
    const z: [number, number] = slab ? [inPlane ? planeZ : cz, thickness] : [cz, sz];
    const draft: SceneBox = { center: [s.center[0], s.center[1], z[0]], size: [s.size[0], s.size[1], z[1]] };
    const { box, clipped } = clip(draft, domain, [0, 1]);
    return { s, n, ramp, box, clipped, inPlane, slab: slab && inPlane };
  });
  // Pass 2 (2D): stagger the heights of overlapping slab-thick boxes, later on top.
  const levels = drafts.map(() => 0);
  drafts.forEach((d, i) => {
    if (!d.slab) return;
    let level = 1;
    for (let j = 0; j < i; j++) {
      const other = drafts[j];
      if (other?.slab && overlapsInPlane(d.box, other.box)) level = Math.max(level, (levels[j] ?? 0) + 1);
    }
    levels[i] = level;
  });
  const maxLevel = Math.max(1, ...levels);
  const step = Math.min(STAGGER_STEP, STAGGER_MAX / maxLevel);
  return drafts.map((d, i) => {
    const size: Vec3 = [...d.box.size];
    if (d.slab) size[2] = thickness * (1 + step * (levels[i] ?? 1));
    return {
      id: d.s.id,
      name: d.s.name,
      mediumId: d.s.medium_id,
      n: d.n,
      color: d.ramp.color,
      opacity: d.inPlane ? d.ramp.opacity : d.ramp.opacity * GHOST_OPACITY,
      center: d.box.center,
      size,
      clipped: d.clipped,
      inPlane: d.inPlane,
    };
  });
}

/** The display boxes, markers and wireframes of a Preview, in µm. */
export function buildScene(preview: Preview): Scene {
  const is2d = preview.is_2d;
  const planeZ = preview.plane_z;
  const thickness = is2d ? displayThickness(preview) : preview.region.size[2];
  const [cx, cy, cz] = preview.region.center;
  const [sx, sy] = preview.region.size;
  const regionCenter: Vec3 = is2d ? [cx, cy, planeZ] : [cx, cy, cz];
  const regionSize: Vec3 = [sx, sy, thickness];
  const background = indexColor(preview.background.n);
  const region: SceneRegion = {
    id: "grid",
    center: regionCenter,
    size: regionSize,
    color: background.color,
    opacity: REGION_OPACITY * background.opacity,
  };

  // The PML shell: x slabs span the full y and z extent, y slabs the region's x and the
  // full z, z slabs (3D only) the region's x and y; so the slabs tile without overlap.
  const [tx, ty, tzRaw] = preview.pml.thickness;
  const tz = is2d ? 0 : tzRaw;
  const [rsx, rsy, rsz] = regionSize;
  const pml: ScenePml[] = [];
  const add = (face: PmlFace, axis: number, size: Vec3, t: number) => {
    if (t <= 0) return;
    const sign = face.endsWith("+") ? 1 : -1;
    const center: Vec3 = [...regionCenter];
    center[axis] = (center[axis] ?? 0) + (sign * ((regionSize[axis] ?? 0) + t)) / 2;
    pml.push({ id: "boundary", face, center, size });
  };
  add("x-", 0, [tx, rsy + 2 * ty, rsz + 2 * tz], tx);
  add("x+", 0, [tx, rsy + 2 * ty, rsz + 2 * tz], tx);
  add("y-", 1, [rsx, ty, rsz + 2 * tz], ty);
  add("y+", 1, [rsx, ty, rsz + 2 * tz], ty);
  add("z-", 2, [rsx, rsy, tz], tz);
  add("z+", 2, [rsx, rsy, tz], tz);

  const domain = boxBounds({ center: regionCenter, size: [rsx + 2 * tx, rsy + 2 * ty, rsz + 2 * tz] });
  const structures = structureBoxes(preview, domain, thickness);

  const tallest = Math.max(thickness, ...structures.filter((s) => s.inPlane).map((s) => s.size[2]));
  const monitorThickness = tallest + MONITOR_LIFT * thickness;
  const monitors: SceneMonitor[] = preview.monitors.map((m) => {
    const size: Vec3 = [...m.size];
    if (is2d && m.geometry !== "point") size[2] = monitorThickness;
    const axes = size.filter((v) => v > 0).length;
    return {
      id: m.id,
      name: m.name,
      geometry: m.geometry,
      shape: SHAPES[axes] ?? "box",
      center: [...m.center],
      size,
      color: MONITOR_COLOR,
    };
  });

  const sources: SceneSource[] = preview.sources.map((s) => ({
    id: s.id,
    name: s.name,
    position: [...s.center],
    component: s.component,
    axis: AXIS[s.component],
    color: s.component.startsWith("E") ? SOURCE_E_COLOR : SOURCE_H_COLOR,
  }));

  const bounds =
    unionBounds([
      domain,
      ...structures.map(boxBounds),
      ...monitors.map(boxBounds),
      ...sources.map((s) => pointBounds(s.position)),
    ]) ?? domain;
  const extent = Math.max(...[0, 1, 2].map((k) => (bounds.max[k] ?? 0) - (bounds.min[k] ?? 0)), 1e-9);

  return {
    is2d,
    planeZ,
    thickness,
    region,
    pml,
    structures,
    sources,
    monitors,
    bounds,
    extent,
    markerRadius: MARKER_FRACTION * extent,
  };
}

// ---------------------------------------------------------------------------------------
// Selection, visibility, picking

/**
 * The boxes that outline a selection: the region for `grid`, the PML slabs for `boundary`,
 * every box of a medium for `medium:<i>`, a marker-sized cube for a source or point monitor.
 */
export function selectionBoxes(scene: Scene, id: string | null): SceneBox[] {
  if (id === null) return [];
  if (id === scene.region.id) return [scene.region];
  if (id === "boundary") return scene.pml;
  const ofMedium = scene.structures.filter((s) => s.mediumId === id);
  if (ofMedium.length > 0) return ofMedium;
  const structure = scene.structures.find((s) => s.id === id);
  if (structure) return [structure];
  const marker = (center: Vec3, scale: number): SceneBox => {
    const side = 2 * scale * scene.markerRadius;
    return { center, size: [side, side, side] };
  };
  const source = scene.sources.find((s) => s.id === id);
  if (source) return [marker(source.position, 1.4)];
  const monitor = scene.monitors.find((m) => m.id === id);
  if (monitor) return [monitor.shape === "point" ? marker(monitor.center, 1.6) : monitor];
  return [];
}

/**
 * The box the camera frames for a selection: the union of its outline boxes, or the whole
 * scene when nothing (or an unknown id) is selected. A selection smaller than 15 % of the
 * scene is grown to a cube of that size, so a point is framed with its surroundings.
 */
export function frameBox(scene: Scene, id: string | null): Bounds {
  const bounds = unionBounds(selectionBoxes(scene, id).map(boxBounds)) ?? scene.bounds;
  const { center, size } = boundsBox(bounds);
  const minimum = MIN_FRAME_FRACTION * scene.extent;
  if (Math.max(...size) >= minimum) return bounds;
  return boxBounds({ center, size: size.map((v) => Math.max(v, minimum)) as Vec3 });
}

/** Ids that are drawn: not hidden themselves, and (boxes) not hidden through their medium. */
export function visibleIds(scene: Scene, hidden: ReadonlySet<string>): Set<string> {
  const ids = new Set<string>();
  const show = (id: string, ...also: string[]) => {
    if (!hidden.has(id) && also.every((a) => !hidden.has(a))) ids.add(id);
  };
  show(scene.region.id);
  if (scene.pml.length > 0) show("boundary");
  for (const s of scene.structures) show(s.id, s.mediumId);
  for (const s of scene.sources) show(s.id);
  for (const m of scene.monitors) show(m.id);
  return ids;
}

/** What a pick hit belongs to; markers are sources and point monitors. */
export type PickKind = "source" | "marker" | "structure" | "monitor" | "pml" | "region";

export interface PickHit {
  id: string;
  kind: PickKind;
  /** Distance from the camera along the ray. */
  distance: number;
}

/**
 * Small things before big ones: a click selects a marker over the box it sits in, a box
 * over the monitor or the PML it is seen through, and the region only when nothing else
 * is under the pointer. Within a kind, the nearest wins.
 */
export const PICK_PRIORITY: Record<PickKind, number> = {
  source: 5,
  marker: 4,
  structure: 3,
  monitor: 2,
  pml: 1,
  region: 0,
};

export function pickId(hits: readonly PickHit[]): string | null {
  let best: PickHit | null = null;
  for (const hit of hits) {
    if (
      best === null ||
      PICK_PRIORITY[hit.kind] > PICK_PRIORITY[best.kind] ||
      (PICK_PRIORITY[hit.kind] === PICK_PRIORITY[best.kind] && hit.distance < best.distance)
    ) {
      best = hit;
    }
  }
  return best?.id ?? null;
}

// ---------------------------------------------------------------------------------------
// Camera

/** iso: the 3/4 view on mount; top (XY), front (XZ), side (YZ): keys 1, 2, 3. */
export type ViewName = "iso" | "top" | "front" | "side";

/** Up on screen is +z in every view but top, where it is +y. */
export const CAMERA_UP: Vec3 = [0, 0, 1];

function normalize(v: Vec3): Vec3 {
  const length = Math.hypot(...v) || 1;
  return v.map((c) => c / length) as Vec3;
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

/** From azimuth (from +x towards +y) and elevation, degrees. */
function fromAngles(azimuth: number, elevation: number): Vec3 {
  const a = (azimuth * Math.PI) / 180;
  const e = (elevation * Math.PI) / 180;
  return [Math.cos(e) * Math.cos(a), Math.cos(e) * Math.sin(a), Math.sin(e)];
}

/**
 * Unit vector from the target to the camera. The 3/4 view looks from the front right,
 * 35° up (55° for a 2D slab, so the plane reads). Top is tilted by 0.06° so that +z,
 * the orbit axis, still projects to +y on screen.
 */
export function viewDirection(view: ViewName, is2d: boolean): Vec3 {
  switch (view) {
    case "iso":
      return normalize(fromAngles(-55, is2d ? 55 : 35));
    case "top":
      return normalize([0, -1e-3, 1]);
    case "front":
      return [0, -1, 0];
    case "side":
      return [1, 0, 0];
  }
}

export interface CameraPose {
  position: Vec3;
  target: Vec3;
  /** Orthographic zoom: CSS pixels per µm. */
  zoom: number;
}

/**
 * An orthographic camera looking along −`direction` at the centre of `bounds`, zoomed so
 * the box's projection fills the viewport less a margin (1.15 leaves 7.5 % on each side),
 * placed `distance` µm from its target.
 */
export function fitCamera(
  bounds: Bounds,
  direction: Vec3,
  width: number,
  height: number,
  distance: number,
  margin = 1.15,
): CameraPose {
  const { center } = boundsBox(bounds);
  const forward = normalize(direction.map((c) => -c) as Vec3);
  const right = normalize(cross(forward, CAMERA_UP));
  const up = cross(right, forward);
  let halfWidth = 0;
  let halfHeight = 0;
  for (const x of [bounds.min[0], bounds.max[0]]) {
    for (const y of [bounds.min[1], bounds.max[1]]) {
      for (const z of [bounds.min[2], bounds.max[2]]) {
        const corner: Vec3 = [x - center[0], y - center[1], z - center[2]];
        halfWidth = Math.max(halfWidth, Math.abs(dot(corner, right)));
        halfHeight = Math.max(halfHeight, Math.abs(dot(corner, up)));
      }
    }
  }
  const tiny = 1e-9;
  const zoom = Math.min(
    Math.max(width, 1) / (2 * Math.max(halfWidth, tiny) * margin),
    Math.max(height, 1) / (2 * Math.max(halfHeight, tiny) * margin),
  );
  const unit = normalize(direction);
  return {
    position: center.map((c, k) => c + (unit[k] ?? 0) * distance) as Vec3,
    target: center,
    zoom,
  };
}

/** Radius of the sphere around `bounds`. */
export function boundsRadius(bounds: Bounds): number {
  const { size } = boundsBox(bounds);
  return Math.max(Math.hypot(...size) / 2, 1e-9);
}
