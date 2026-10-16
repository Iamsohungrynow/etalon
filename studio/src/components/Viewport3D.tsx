import { Canvas, type RootState, type ThreeEvent } from "@react-three/fiber";
import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BoxGeometry,
  BufferGeometry,
  Color,
  ConeGeometry,
  DoubleSide,
  Float32BufferAttribute,
  FrontSide,
  Group,
  LineBasicMaterial,
  LineDashedMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshLambertMaterial,
  OctahedronGeometry,
  OrthographicCamera,
  ShaderMaterial,
  SphereGeometry,
  Vector3,
  type Material,
  type Object3D,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { isDarkTokens, readTokens, token, useThemeVersion } from "../charts/theme";
import {
  boundsRadius,
  boxEdgeSegments,
  buildScene,
  CAMERA_UP,
  fitCamera,
  frameBox,
  pickId,
  selectionBoxes,
  viewDirection,
  visibleIds,
  type PickHit,
  type PickKind,
  type Preview,
  type Scene,
  type SceneBox,
  type Vec3,
  type ViewName,
} from "../viewport/scene";
import { SizeWatcher } from "../viewport/SizeWatcher";
import { cx } from "./cx";

export interface Viewport3DProps {
  /** Accessible name of the viewport. */
  label: string;
  preview: Preview;
  selectedId: string | null;
  /** Preview ids not drawn (a medium id hides all its boxes). */
  hiddenIds: ReadonlySet<string>;
  /** A click on an object selects its Preview id; a click on empty space selects null. */
  onSelect: (id: string | null) => void;
  /** Change it to frame the selection (or the whole scene when nothing is selected). */
  frameRequest?: number;
  className?: string;
}

/** Colours from the theme tokens; the boxes' own colours come from the index ramp. */
interface Palette {
  background: string;
  edge: string;
  regionEdge: string;
  pml: string;
  selection: string;
}

function palette(tokens: Record<string, string>): Palette {
  return {
    // The reference's black void: bg on dark, a slightly darker paper on light.
    background: isDarkTokens(tokens) ? token(tokens, "bg") : token(tokens, "raised"),
    edge: token(tokens, "rule"),
    regionEdge: token(tokens, "control"),
    pml: token(tokens, "muted"),
    selection: token(tokens, "accent-ink"),
  };
}

const KEY_VIEWS: Record<string, ViewName> = { "1": "top", "2": "front", "3": "side" };
/** A pointer that moved more than this (px) between down and up orbited; it selects nothing. */
const CLICK_SLOP = 4;
const MARKER_ORDER = 10;
const SELECTION_ORDER = 20;
/** Lambert lights, in three's physical units (π = full albedo): top faces show the ramp colour. */
const AMBIENT = 0.72 * Math.PI;
const KEY_LIGHT = 0.4 * Math.PI;

const noRaycast = () => {};

function segmentsGeometry(positions: number[]): BufferGeometry {
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  return geometry;
}

/** Edges at the origin of a box centred there, positioned by the caller. */
function localEdges(size: Vec3): number[] {
  return boxEdgeSegments({ center: [0, 0, 0], size });
}

/**
 * A screen-space diagonal hatch (constant 7 px pitch at any zoom, so it never moirés): the
 * PML shell reads as "not part of the device" without hiding what is behind it.
 */
function hatchMaterial(color: string, pixelRatio: number): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      color: { value: new Color(color) },
      pitch: { value: 7 * pixelRatio },
      width: { value: Math.max(1, pixelRatio) },
    },
    vertexShader: /* glsl */ `
      void main() {
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 color;
      uniform float pitch;
      uniform float width;
      void main() {
        float s = mod(gl_FragCoord.x + gl_FragCoord.y, pitch);
        gl_FragColor = vec4(color, s < width ? 0.55 : 0.06);
        #include <colorspace_fragment>
      }`,
    transparent: true,
    depthWrite: false,
    side: FrontSide,
  });
}

/**
 * The three.js objects of a Scene, built once per scene and theme. Visibility and the
 * selection outline change in place, so a click costs no rebuild.
 */
class ViewportObjects {
  readonly root = new Group();
  private readonly overlay = new Group();
  private readonly byId = new Map<string, Object3D[]>();
  private readonly owned: (BufferGeometry | Material)[] = [];
  private readonly selection: LineMaterial;

  constructor(
    private readonly scene: Scene,
    colors: Palette,
    pixelRatio: number,
  ) {
    this.selection = this.own(
      new LineMaterial({
        color: colors.selection,
        linewidth: 2,
        depthTest: false,
        depthWrite: false,
        transparent: true,
      }),
    );
    this.addRegion(colors);
    this.addPml(colors, pixelRatio);
    for (const s of scene.structures) this.addStructure(s, colors);
    for (const s of scene.sources) this.addSource(s.id, s.position, s.axis, s.color);
    for (const m of scene.monitors) this.addMonitor(m);
    this.overlay.raycast = noRaycast;
    this.root.add(this.overlay);
  }

  private own<T extends BufferGeometry | Material>(thing: T): T {
    this.owned.push(thing);
    return thing;
  }

  private register(id: string, kind: PickKind, ...objects: Object3D[]) {
    for (const object of objects) {
      object.userData = { pickId: id, pickKind: kind };
      this.root.add(object);
    }
    this.byId.set(id, [...(this.byId.get(id) ?? []), ...objects]);
  }

  private edges(box: SceneBox, color: string, opacity = 1): LineSegments {
    const lines = new LineSegments(
      this.own(segmentsGeometry(localEdges(box.size))),
      this.own(new LineBasicMaterial({ color, transparent: opacity < 1, opacity })),
    );
    lines.position.set(...box.center);
    lines.raycast = noRaycast;
    return lines;
  }

  private box(box: SceneBox, material: Material, renderOrder = 0): Mesh {
    const mesh = new Mesh(this.own(new BoxGeometry(...box.size)), this.own(material));
    mesh.position.set(...box.center);
    mesh.renderOrder = renderOrder;
    return mesh;
  }

  private addRegion(colors: Palette) {
    const { region } = this.scene;
    const slab = this.box(
      region,
      new MeshBasicMaterial({
        color: region.color,
        transparent: true,
        opacity: region.opacity,
        depthWrite: false,
      }),
    );
    this.register(region.id, "region", slab, this.edges(region, colors.regionEdge));
  }

  private addPml(colors: Palette, pixelRatio: number) {
    for (const slab of this.scene.pml) {
      const mesh = this.box(slab, hatchMaterial(colors.pml, pixelRatio));
      this.register(slab.id, "pml", mesh, this.edges(slab, colors.edge));
    }
  }

  /**
   * A translucent box (air, oxide) still writes depth and is drawn before the translucent
   * region slab, so it cuts the slab out where it is: an air hole in a silicon background
   * reads as a hole, not as a tinted patch of silicon.
   */
  private addStructure(s: Scene["structures"][number], colors: Palette) {
    const translucent = s.opacity < 1;
    const mesh = this.box(
      s,
      new MeshLambertMaterial({
        color: s.color,
        flatShading: true,
        transparent: translucent,
        opacity: s.opacity,
      }),
      translucent ? -1 : 0,
    );
    this.register(s.id, "structure", mesh, this.edges(s, colors.edge, s.inPlane ? 1 : 0.5));
  }

  /** A sphere and an arrow along the component's axis, drawn over everything. */
  private addSource(id: string, position: Vec3, axis: Vec3, color: string) {
    const r = this.scene.markerRadius;
    const length = 6 * r;
    const head = 2 * r;
    const marker = () =>
      this.own(new MeshBasicMaterial({ color, depthTest: false, depthWrite: false, transparent: true }));
    const sphere = new Mesh(this.own(new SphereGeometry(r, 20, 14)), marker());
    const shaft = new LineSegments(
      this.own(segmentsGeometry([0, 0, 0, ...axis.map((c) => c * (length - head))])),
      this.own(new LineBasicMaterial({ color, depthTest: false, depthWrite: false, transparent: true })),
    );
    shaft.raycast = noRaycast;
    // ConeGeometry points along +y; turn it onto the axis and put its tip at `length`.
    const cone = new Mesh(this.own(new ConeGeometry(0.7 * r, head, 16)), marker());
    cone.quaternion.setFromUnitVectors(new Vector3(0, 1, 0), new Vector3(...axis));
    cone.position.set(...(axis.map((c) => c * (length - head / 2)) as Vec3));
    const group = new Group();
    group.position.set(...position);
    for (const part of [sphere, shaft, cone]) {
      part.renderOrder = MARKER_ORDER;
      group.add(part);
    }
    this.register(id, "source", group);
  }

  private addMonitor(m: Scene["monitors"][number]) {
    const r = this.scene.markerRadius;
    if (m.shape === "point") {
      const diamond = new OctahedronGeometry(1.4 * r);
      const lines = new LineSegments(
        this.own(segmentsGeometry([...this.edgePositions(diamond)])),
        this.own(new LineBasicMaterial({ color: m.color, depthTest: false, transparent: true })),
      );
      lines.renderOrder = MARKER_ORDER;
      lines.raycast = noRaycast;
      const proxy = new Mesh(this.own(diamond), this.own(new MeshBasicMaterial({ visible: false })));
      for (const object of [lines, proxy]) object.position.set(...m.center);
      this.register(m.id, "marker", lines, proxy);
      return;
    }
    const dash = 0.012 * this.scene.extent;
    const lines = new LineSegments(
      this.own(segmentsGeometry(localEdges(m.size))),
      this.own(new LineDashedMaterial({ color: m.color, dashSize: dash, gapSize: 0.6 * dash })),
    );
    lines.computeLineDistances();
    lines.position.set(...m.center);
    lines.raycast = noRaycast;
    // An invisible box to click on; flat sides get a little depth so a ray can hit them.
    const floor = 0.5 * r;
    const proxy = this.box(
      { center: m.center, size: m.size.map((v) => Math.max(v, floor)) as Vec3 },
      new MeshBasicMaterial({ visible: false, side: DoubleSide }),
    );
    this.register(m.id, "monitor", lines, proxy);
  }

  /** Every triangle edge of an octahedron, once: its 12 edges. */
  private edgePositions(geometry: BufferGeometry): number[] {
    const p = geometry.getAttribute("position");
    const out: number[] = [];
    const seen = new Set<string>();
    for (let t = 0; t < p.count; t += 3) {
      for (const [a, b] of [[t, t + 1], [t + 1, t + 2], [t + 2, t]] as const) {
        const pa = [p.getX(a), p.getY(a), p.getZ(a)];
        const pb = [p.getX(b), p.getY(b), p.getZ(b)];
        const key = [pa, pb].map((v) => v.map((c) => c.toFixed(6)).join(",")).sort().join("|");
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(...pa, ...pb);
      }
    }
    return out;
  }

  setVisible(visible: ReadonlySet<string>) {
    for (const [id, objects] of this.byId) {
      for (const object of objects) object.visible = visible.has(id);
    }
  }

  /** A 2 px accent-ink outline around each box, drawn over everything. */
  setSelection(boxes: readonly SceneBox[]) {
    for (const child of [...this.overlay.children]) {
      if (child instanceof LineSegments2) child.geometry.dispose();
      this.overlay.remove(child);
    }
    const positions = boxes.flatMap((b) => boxEdgeSegments(b));
    if (positions.length === 0) return;
    const geometry = new LineSegmentsGeometry();
    geometry.setPositions(positions);
    const outline = new LineSegments2(geometry, this.selection);
    outline.renderOrder = SELECTION_ORDER;
    outline.raycast = noRaycast;
    this.overlay.add(outline);
  }

  dispose() {
    this.setSelection([]);
    for (const thing of this.owned) thing.dispose();
  }
}

/** The pick target of a hit: the nearest ancestor that carries a Preview id, if all are shown. */
function pickTarget(object: Object3D | null): { id: string; kind: PickKind } | null {
  let found: { id: string; kind: PickKind } | null = null;
  for (let o = object; o; o = o.parent) {
    if (!o.visible) return null;
    const { pickId: id, pickKind: kind } = o.userData as { pickId?: string; pickKind?: PickKind };
    if (!found && id && kind) found = { id, kind };
  }
  return found;
}

/** The boxes to outline: the selection's, minus what is hidden. */
function outlineBoxes(scene: Scene, id: string | null, visible: ReadonlySet<string>): SceneBox[] {
  if (id === null) return [];
  const ofMedium = scene.structures.filter((s) => s.mediumId === id);
  if (ofMedium.length > 0) return ofMedium.filter((s) => visible.has(s.id));
  return visible.has(id) ? selectionBoxes(scene, id) : [];
}

/** Point the orthographic camera along `direction` at what `id` frames, and redraw. */
function frameCamera(
  root: RootState,
  controls: OrbitControls | null,
  scene: Scene,
  direction: Vec3,
  id: string | null,
) {
  const state = root.get();
  const camera = state.camera;
  const radius = boundsRadius(scene.bounds);
  const pose = fitCamera(frameBox(scene, id), direction, state.size.width, state.size.height, 4 * radius);
  camera.up.set(...CAMERA_UP);
  camera.position.set(...pose.position);
  camera.near = 0.1 * radius;
  camera.far = 12 * radius;
  if (camera instanceof OrthographicCamera) camera.zoom = pose.zoom;
  camera.lookAt(...pose.target);
  camera.updateProjectionMatrix();
  if (controls) {
    controls.target.set(...pose.target);
    controls.update();
  }
  state.invalidate();
}

/** The current direction from the orbit target to the camera. */
function currentDirection(root: RootState, controls: OrbitControls | null, scene: Scene): Vec3 {
  const { camera } = root.get();
  if (!controls) return viewDirection("iso", scene.is2d);
  const d = camera.position.clone().sub(controls.target);
  if (d.lengthSq() === 0) return viewDirection("iso", scene.is2d);
  d.normalize();
  return [d.x, d.y, d.z];
}

/**
 * The Setup viewport (ui-ux-spec §5.2): the region slab, the hatched PML shell, the boxes
 * coloured by refractive index, sources as spheres with an arrow along their component,
 * monitors as dashed wireframes. Orthographic, orbit/pan/zoom; 1/2/3 top/front/side, F
 * frames. Rendered on demand only: idle when nothing changes.
 */
export function Viewport3D({
  label,
  preview,
  selectedId,
  hiddenIds,
  onSelect,
  frameRequest,
  className,
}: Viewport3DProps) {
  const scene = useMemo(() => buildScene(preview), [preview]);
  const themeVersion = useThemeVersion();
  const colors = useMemo(() => palette(readTokensAt(themeVersion)), [themeVersion]);
  const objects = useMemo(
    () => new ViewportObjects(scene, colors, Math.min(2, Math.max(1, window.devicePixelRatio || 1))),
    [scene, colors],
  );
  const [root, setRoot] = useState<RootState | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const selectedRef = useRef(selectedId);
  const framedRef = useRef(false);
  const frameRequestRef = useRef(frameRequest);

  useEffect(() => () => objects.dispose(), [objects]);

  useEffect(() => {
    selectedRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    const visible = visibleIds(scene, hiddenIds);
    objects.setVisible(visible);
    objects.setSelection(outlineBoxes(scene, selectedId, visible));
    root?.invalidate();
  }, [objects, scene, hiddenIds, selectedId, root]);

  // Orbit controls, calm: no damping, so nothing moves after the pointer stops.
  useEffect(() => {
    if (!root) return;
    const controls = new OrbitControls(root.camera, root.gl.domElement);
    controls.enableDamping = false;
    controls.screenSpacePanning = true;
    controls.zoomToCursor = true;
    const redraw = () => root.invalidate();
    controls.addEventListener("change", redraw);
    controlsRef.current = controls;
    return () => {
      controls.removeEventListener("change", redraw);
      controls.dispose();
      controlsRef.current = null;
    };
  }, [root]);

  // The 3/4 view of the whole scene, once the canvas has a size (it is measured after it
  // is created; framing earlier fits the camera to 0 × 0 and draws nothing). Later size
  // changes just redraw.
  const onSize = useCallback(() => {
    if (!root) return;
    if (framedRef.current) {
      root.invalidate();
      return;
    }
    framedRef.current = true;
    frameCamera(root, controlsRef.current, scene, viewDirection("iso", scene.is2d), null);
  }, [root, scene]);

  // A new frameRequest frames the selection from where the camera looks now.
  useEffect(() => {
    if (!root || frameRequest === frameRequestRef.current) return;
    frameRequestRef.current = frameRequest;
    const controls = controlsRef.current;
    frameCamera(root, controls, scene, currentDirection(root, controls, scene), selectedRef.current);
  }, [root, frameRequest, scene]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!root || event.ctrlKey || event.metaKey || event.altKey) return;
    const controls = controlsRef.current;
    const view = KEY_VIEWS[event.key];
    if (view) {
      frameCamera(root, controls, scene, viewDirection(view, scene.is2d), null);
    } else if (event.key === "f" || event.key === "F") {
      frameCamera(root, controls, scene, currentDirection(root, controls, scene), selectedId);
    } else {
      return;
    }
    event.preventDefault();
  };

  const onClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    if (event.delta > CLICK_SLOP) return;
    const hits: PickHit[] = [];
    for (const hit of event.intersections) {
      const target = pickTarget(hit.object);
      if (target) hits.push({ ...target, distance: hit.distance });
    }
    onSelect(pickId(hits));
  };

  return (
    <div
      role="img"
      aria-label={label}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className={cx("relative h-full w-full cursor-crosshair", className)}
      style={{ background: colors.background }}
    >
      <Canvas
        orthographic
        flat
        frameloop="demand"
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        camera={{ position: [0, -10, 10], up: CAMERA_UP, zoom: 40, near: 0.01, far: 1000 }}
        onCreated={setRoot}
        onPointerMissed={() => onSelect(null)}
        style={{ position: "absolute", inset: 0 }}
      >
        <ambientLight intensity={AMBIENT} />
        <directionalLight position={[0.4, -0.6, 1]} intensity={KEY_LIGHT} />
        <primitive object={objects.root} onClick={onClick} />
        <SizeWatcher onSize={onSize} />
      </Canvas>
    </div>
  );
}

/** readTokens(), keyed on the theme version so a memo re-reads it when the theme changes. */
function readTokensAt(themeVersion: number): Record<string, string> {
  void themeVersion;
  return readTokens();
}
