// The viewport's scene, built from a Preview without WebGL: counts, positions in µm, the 2D
// display thickness, the index colour ramp, selection framing, picking and camera fitting.
import { describe, expect, it } from "vitest";
import {
  boxBounds,
  boxEdgeSegments,
  buildScene,
  fitCamera,
  frameBox,
  indexColor,
  MONITOR_COLOR,
  pickId,
  selectionBoxes,
  SOURCE_E_COLOR,
  SOURCE_H_COLOR,
  viewDirection,
  visibleIds,
  warmth,
  type Preview,
  type Vec3,
} from "./scene";

/** A 2D TE preview: an 8 × 4 µm region, 1 µm of PML, a Si core in a SiO2 box. */
function preview2d(): Preview {
  return {
    is_2d: true,
    plane_z: 0,
    region: { center: [0, 0, 0], size: [8, 4, 0] },
    pml: { layers: 50, thickness: [1, 1, 0] },
    background: { n: 1, name: "air" },
    media: [
      { id: "medium:0", name: "SiO2", n: 1.444 },
      { id: "medium:1", name: "Si", n: 3.476 },
    ],
    structures: [
      {
        id: "structure:0",
        name: "cladding",
        kind: "Box",
        center: [0, 0, 0],
        size: [6, 3, 0],
        medium_id: "medium:0",
      },
      {
        // Longer than region + PML (10 µm): cut to the domain.
        id: "structure:1",
        name: "core",
        kind: "Box",
        center: [0, 0, 0],
        size: [12, 0.5, 0],
        medium_id: "medium:1",
      },
    ],
    sources: [
      {
        id: "source:0",
        name: "dipole",
        kind: "PointSource",
        center: [-3, 0.05, 0],
        component: "Hz",
        wavelength_um: 1.55,
        bandwidth_um: 0.3,
      },
    ],
    monitors: [
      {
        id: "monitor:field",
        name: "field",
        kind: "DFTMonitor",
        geometry: "plane",
        center: [0, 0, 0],
        size: [7.6, 3.6, 0],
        wavelengths_um: [1.5, 1.55, 1.6],
        components: ["Ex", "Ey", "Hz"],
      },
      {
        id: "monitor:end",
        name: "end",
        kind: "DFTMonitor",
        geometry: "point",
        center: [3, 0, 0],
        size: [0, 0, 0],
        wavelengths_um: [1.55],
        components: ["Hz"],
      },
    ],
    grid: {
      dx: 0.02,
      dy: 0.02,
      nx: 500,
      ny: 300,
      region_cells: [400, 200],
      dt_s: 4.6e-17,
      courant: 0.99,
      steps: 2600,
    },
  };
}

const T = 0.32; // max(0.04 × 8 µm, 2 × 0.02 µm)

function close(actual: readonly number[], expected: readonly number[]) {
  expect(actual).toHaveLength(expected.length);
  actual.forEach((v, i) => expect(v).toBeCloseTo(expected[i] ?? Number.NaN, 9));
}

describe("buildScene, 2D", () => {
  const scene = buildScene(preview2d());

  it("has the region, four PML slabs and one object per structure, source and monitor", () => {
    expect(scene.is2d).toBe(true);
    expect(scene.pml).toHaveLength(4);
    expect(scene.structures.map((s) => s.id)).toEqual(["structure:0", "structure:1"]);
    expect(scene.sources.map((s) => s.id)).toEqual(["source:0"]);
    expect(scene.monitors.map((m) => m.id)).toEqual(["monitor:field", "monitor:end"]);
  });

  it("draws the plane as a slab of the display thickness", () => {
    expect(scene.thickness).toBeCloseTo(T, 12);
    expect(scene.region.id).toBe("grid");
    close(scene.region.center, [0, 0, 0]);
    close(scene.region.size, [8, 4, T]);
    // A coarse grid sets the floor: 2 dx.
    const coarse = preview2d();
    if (coarse.grid) coarse.grid.dx = 0.5;
    expect(buildScene(coarse).thickness).toBeCloseTo(1.0, 12);
    // Without a grid, the size alone.
    expect(buildScene({ ...preview2d(), grid: null }).thickness).toBeCloseTo(T, 12);
  });

  it("tiles the PML around the region in the plane, from pml.thickness", () => {
    const byFace = Object.fromEntries(scene.pml.map((p) => [p.face, p]));
    expect(Object.keys(byFace).sort()).toEqual(["x+", "x-", "y+", "y-"]);
    expect(scene.pml.every((p) => p.id === "boundary")).toBe(true);
    close(byFace["x-"]?.center ?? [], [-4.5, 0, 0]);
    close(byFace["x+"]?.size ?? [], [1, 6, T]);
    close(byFace["y-"]?.center ?? [], [0, -2.5, 0]);
    close(byFace["y+"]?.size ?? [], [8, 1, T]);
  });

  it("draws flat boxes at the display thickness, later overlapping ones a little taller", () => {
    const [cladding, core] = scene.structures;
    close(cladding?.center ?? [], [0, 0, 0]);
    close(cladding?.size ?? [], [6, 3, T * 1.04]);
    expect(cladding?.clipped).toBe(false);
    // Cut to the domain (±5 µm in x) and one stagger level above the cladding it overlaps.
    close(core?.size ?? [], [10, 0.5, T * 1.08]);
    expect(core?.clipped).toBe(true);
    expect(core?.inPlane).toBe(true);
  });

  it("keeps a thin box's own z extent and ghosts one outside the plane", () => {
    const p = preview2d();
    const [first, second] = p.structures;
    if (!first || !second) throw new Error("fixture");
    first.size = [6, 3, 0.22];
    second.center = [0, 0, 1];
    second.size = [4, 0.5, 0.22];
    const [thin, off] = buildScene(p).structures;
    close(thin?.size ?? [], [6, 3, 0.22]);
    expect(off?.inPlane).toBe(false);
    close(off?.center ?? [], [0, 0, 1]);
    expect(off?.opacity ?? 1).toBeLessThan(indexColor(3.476).opacity);
  });

  it("colours by refractive index: silicon warm, silica cool, air nearly clear", () => {
    const [cladding, core] = scene.structures;
    expect(core?.n).toBe(3.476);
    expect(warmth(core?.color ?? "")).toBeGreaterThan(0);
    expect(warmth(cladding?.color ?? "")).toBeLessThan(0);
    expect(warmth(core?.color ?? "")).toBeGreaterThan(warmth(cladding?.color ?? ""));
    expect(indexColor(1).opacity).toBeLessThan(indexColor(1.444).opacity);
    // Warmer with n from silica up, more opaque with n throughout, clamped at both ends.
    const w = [1.444, 2, 2.5, 3, 4].map((n) => warmth(indexColor(n).color));
    for (let i = 1; i < w.length; i++) expect(w[i] ?? 0).toBeGreaterThanOrEqual(w[i - 1] ?? 0);
    const o = [1, 1.2, 1.444, 2, 3].map((n) => indexColor(n).opacity);
    for (let i = 1; i < o.length; i++) expect(o[i] ?? 0).toBeGreaterThan(o[i - 1] ?? 0);
    expect(indexColor(4)).toEqual(indexColor(3));
    expect(indexColor(0.5)).toEqual(indexColor(1));
    // The region takes the background medium's colour, translucent.
    expect(scene.region.color).toBe(indexColor(1).color);
    expect(scene.region.opacity).toBeLessThan(indexColor(1).opacity);
  });

  it("places sources with their component axis and monitors as boxes or points", () => {
    const [source] = scene.sources;
    close(source?.position ?? [], [-3, 0.05, 0]);
    expect(source?.axis).toEqual([0, 0, 1]); // Hz
    expect(source?.color).toBe(SOURCE_H_COLOR);
    const [field, end] = scene.monitors;
    expect(field?.shape).toBe("box");
    // Above the tallest box (the core, 1.08 T) so its wireframe shows.
    close(field?.size ?? [], [7.6, 3.6, T * 1.16]);
    expect(field?.color).toBe(MONITOR_COLOR);
    expect(end?.shape).toBe("point");
    close(end?.center ?? [], [3, 0, 0]);
  });

  it("maps every component to its axis and E/H to two colours", () => {
    const p = preview2d();
    const [s] = p.sources;
    if (!s) throw new Error("fixture");
    s.component = "Ex";
    const [ex] = buildScene(p).sources;
    expect(ex?.axis).toEqual([1, 0, 0]);
    expect(ex?.color).toBe(SOURCE_E_COLOR);
    s.component = "Ey";
    expect(buildScene(p).sources[0]?.axis).toEqual([0, 1, 0]);
  });

  it("bounds everything drawn and sizes markers from it", () => {
    close(scene.bounds.min, [-5, -3, (-T * 1.16) / 2]);
    close(scene.bounds.max, [5, 3, (T * 1.16) / 2]);
    expect(scene.extent).toBeCloseTo(10, 12);
    expect(scene.markerRadius).toBeCloseTo(0.12, 12);
  });
});

describe("buildScene, 3D", () => {
  it("has six PML slabs and keeps the region's own z size", () => {
    const p: Preview = {
      ...preview2d(),
      is_2d: false,
      region: { center: [0, 0, 0], size: [8, 4, 2] },
      pml: { layers: 10, thickness: [1, 1, 0.5] },
      grid: null,
    };
    const scene = buildScene(p);
    expect(scene.thickness).toBe(2);
    expect(scene.pml.map((s) => s.face)).toEqual(["x-", "x+", "y-", "y+", "z-", "z+"]);
    const z = scene.pml.find((s) => s.face === "z+");
    close(z?.center ?? [], [0, 0, 1.25]);
    close(z?.size ?? [], [8, 4, 0.5]);
    // A flat box stays flat; the core is cut in x only.
    close(scene.structures[1]?.size ?? [], [10, 0.5, 0]);
  });
});

describe("selection", () => {
  const scene = buildScene(preview2d());

  it("frames a structure by its box and nothing by the whole scene", () => {
    expect(frameBox(scene, "structure:1")).toEqual(boxBounds(scene.structures[1] ?? scene.region));
    expect(frameBox(scene, null)).toEqual(scene.bounds);
    expect(frameBox(scene, "monitor:nope")).toEqual(scene.bounds);
    expect(frameBox(scene, "medium:1")).toEqual(frameBox(scene, "structure:1"));
    const shell = frameBox(scene, "boundary");
    close(shell.min.slice(0, 2), [-5, -3]);
    close(shell.max.slice(0, 2), [5, 3]);
  });

  it("frames a point with its surroundings: a cube of 15 % of the scene", () => {
    const box = frameBox(scene, "monitor:end");
    close(box.min, [3 - 0.75, -0.75, -0.75]);
    close(box.max, [3 + 0.75, 0.75, 0.75]);
  });

  it("outlines a medium as all its boxes", () => {
    expect(selectionBoxes(scene, "medium:0")).toHaveLength(1);
    expect(selectionBoxes(scene, "grid")).toEqual([scene.region]);
    expect(selectionBoxes(scene, "boundary")).toHaveLength(4);
    expect(selectionBoxes(scene, null)).toEqual([]);
  });

  it("hides objects by id, and boxes through their medium", () => {
    const all = visibleIds(scene, new Set());
    expect([...all].sort()).toEqual(
      ["boundary", "grid", "monitor:end", "monitor:field", "source:0", "structure:0", "structure:1"].sort(),
    );
    const some = visibleIds(scene, new Set(["medium:1", "monitor:field"]));
    expect(some.has("structure:1")).toBe(false);
    expect(some.has("monitor:field")).toBe(false);
    expect(some.has("structure:0")).toBe(true);
  });

  it("picks markers over boxes over monitors over the PML and region, then the nearest", () => {
    expect(pickId([])).toBeNull();
    expect(
      pickId([
        { id: "grid", kind: "region", distance: 1 },
        { id: "monitor:field", kind: "monitor", distance: 2 },
        { id: "structure:0", kind: "structure", distance: 5 },
      ]),
    ).toBe("structure:0");
    expect(
      pickId([
        { id: "structure:0", kind: "structure", distance: 5 },
        { id: "structure:1", kind: "structure", distance: 4.9 },
        { id: "source:0", kind: "source", distance: 6 },
      ]),
    ).toBe("source:0");
    expect(
      pickId([
        { id: "structure:0", kind: "structure", distance: 5 },
        { id: "structure:1", kind: "structure", distance: 4.9 },
      ]),
    ).toBe("structure:1");
  });
});

describe("boxEdgeSegments", () => {
  it("gives 12 edges for a box, 4 for a rectangle, 1 for a line and none for a point", () => {
    const count = (size: Vec3) => boxEdgeSegments({ center: [1, 2, 3], size }).length / 6;
    expect(count([2, 2, 2])).toBe(12);
    expect(count([2, 2, 0])).toBe(4);
    expect(count([2, 0, 0])).toBe(1);
    expect(count([0, 0, 0])).toBe(0);
    const [x0, y0, z0, x1, y1, z1] = boxEdgeSegments({ center: [1, 2, 3], size: [2, 0, 0] });
    expect([x0, y0, z0, x1, y1, z1]).toEqual([0, 2, 3, 2, 2, 3]);
  });
});

describe("camera", () => {
  const scene = buildScene(preview2d());

  it("looks down z for the top view with +y up, and along y and x for front and side", () => {
    const top = viewDirection("top", true);
    expect(top[2]).toBeCloseTo(1, 5);
    expect(top[1]).toBeLessThan(0);
    expect(viewDirection("front", true)).toEqual([0, -1, 0]);
    expect(viewDirection("side", true)).toEqual([1, 0, 0]);
    const iso = viewDirection("iso", true);
    expect(Math.hypot(...iso)).toBeCloseTo(1, 12);
    expect(iso[2]).toBeGreaterThan(viewDirection("iso", false)[2]); // steeper for a 2D slab
  });

  it("fits the projected box in the viewport, less the margin", () => {
    const pose = fitCamera(scene.bounds, viewDirection("top", true), 1000, 600, 40);
    // 10 × 6 µm seen from above in 1000 × 600 px: both axes fit at 1000 / (10 × 1.15).
    expect(pose.zoom).toBeCloseTo(1000 / (10 * 1.15), 1);
    close(pose.target, [0, 0, 0]);
    expect(pose.position[2]).toBeCloseTo(40, 3);
    // A narrow viewport is limited by its width.
    const narrow = fitCamera(scene.bounds, viewDirection("front", true), 200, 600, 40);
    expect(narrow.zoom).toBeCloseTo(200 / (10 * 1.15), 6);
    const dir: Vec3 = viewDirection("side", true);
    const side = fitCamera(scene.bounds, dir, 600, 600, 40);
    expect(side.zoom).toBeCloseTo(600 / (6 * 1.15), 6); // y is across the screen
  });
});
