import {
  useEffect,
  useEffectEvent,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type Ref,
} from "react";
import {
  fieldBounds,
  nodePosition,
  renderToImageData,
  sampleAt,
  type ColormapName,
  type Extent,
  type FieldBounds,
  type RenderOptions,
  type ScaleKind,
  type Shape,
} from "../field/render";
import { cx } from "./cx";

/** A structure box in µm, drawn as a 1 px outline over the field. */
export interface FieldOutline {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

/** The node under the cursor: its position in µm, its value and its indices. */
export interface FieldSample {
  x: number;
  y: number;
  value: number;
  i: number;
  j: number;
}

export interface FieldCanvasHandle {
  /** The current view as a PNG, `scale` output pixels per CSS pixel (default 2). */
  toPng(scale?: number): Promise<Blob>;
  /** Back to the whole field, centred (as a double-click does). */
  resetView(): void;
}

export interface FieldCanvasProps {
  /** Accessible name of the image, e.g. "Hz, real part, λ 1.55 µm". */
  label: string;
  /** C order, `data[i * n_y + j]` is node (x_i, y_j) (plan-u1 §13.1). */
  data: Float32Array;
  shape: Shape;
  /** [x_first, x_last, y_first, y_last] of the nodes, µm. */
  extent: Extent;
  colormap: ColormapName;
  scale?: ScaleKind;
  /** ±max|v|, so 0 is the colormap's centre (RdBu). */
  symmetric?: boolean;
  /** Colour limits; the data's finite range when absent. */
  range?: readonly [number, number];
  outlines?: readonly FieldOutline[];
  /** The node under the cursor, or null when the cursor leaves the field. */
  onHover?: (sample: FieldSample | null) => void;
  /** Size the component through this; the canvas fills the box. */
  className?: string;
  ref?: Ref<FieldCanvasHandle>;
}

const NO_OUTLINES: readonly FieldOutline[] = [];
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 1000;
/** Zoom factor per pixel of wheel travel: one 100 px notch ≈ ×1.22. */
const WHEEL_ZOOM = 0.002;
const OUTLINE_ALPHA = 0.6;
/** Used only when the tokens are not loaded (tests): the dark theme's values. */
const FALLBACK_TEXT = "#eceef2";
const FALLBACK_BG = "#0e1013";

/** Zoom 1 fits the whole field; (cx, cy) is the µm at the canvas centre. */
interface View {
  /** The shape and extent the view belongs to; another field starts from the fit. */
  key: string;
  zoom: number;
  cx: number;
  cy: number;
}

/** Everything that places µm on the canvas, in CSS pixels. */
interface Frame {
  width: number;
  height: number;
  shape: Shape;
  bounds: FieldBounds;
  view: View;
}

function fitView(key: string, bounds: FieldBounds): View {
  return { key, zoom: 1, cx: (bounds.xMin + bounds.xMax) / 2, cy: (bounds.yMin + bounds.yMax) / 2 };
}

/** CSS px per µm, equal in x and y so the field keeps its aspect ratio. */
function pxPerUm(frame: Frame): number {
  const { bounds, width, height, view } = frame;
  const fit = Math.min(width / (bounds.xMax - bounds.xMin), height / (bounds.yMax - bounds.yMin));
  return fit * view.zoom;
}

/** CSS px (from the canvas's top-left) → µm; y points up. */
function toUm(frame: Frame, px: number, py: number): [number, number] {
  const s = pxPerUm(frame);
  return [
    frame.view.cx + (px - frame.width / 2) / s,
    frame.view.cy - (py - frame.height / 2) / s,
  ];
}

/** The view zoomed by `factor` about the CSS point (px, py), which stays on the same µm. */
function zoomAbout(frame: Frame, px: number, py: number, factor: number): View {
  const [x, y] = toUm(frame, px, py);
  const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, frame.view.zoom * factor));
  const s = pxPerUm({ ...frame, view: { ...frame.view, zoom } });
  return {
    key: frame.view.key,
    zoom,
    cx: x - (px - frame.width / 2) / s,
    cy: y + (py - frame.height / 2) / s,
  };
}

/** `base` at the canvas's current on-screen size (an event may beat ResizeObserver). */
function liveFrame(canvas: HTMLCanvasElement, base: Frame): Frame {
  const rect = canvas.getBoundingClientRect();
  return { ...base, width: rect.width, height: rect.height };
}

function cssColour(element: Element, token: string, fallback: string): string {
  return getComputedStyle(element).getPropertyValue(token).trim() || fallback;
}

/**
 * Draws the visible part of the field image and the outlines. `ratio` is device (or
 * export) pixels per CSS pixel. Only the visible cells of the source are drawn, so a
 * deep zoom never asks the canvas for a destination millions of pixels wide.
 */
function paint(
  ctx: CanvasRenderingContext2D,
  frame: Frame,
  ratio: number,
  source: HTMLCanvasElement | null,
  outlines: readonly FieldOutline[],
  outlineColour: string,
  background: string | null,
): void {
  const width = Math.round(frame.width * ratio);
  const height = Math.round(frame.height * ratio);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, width, height);
  } else {
    ctx.clearRect(0, 0, width, height); // the container's bg shows through
  }
  const s = pxPerUm(frame) * ratio;
  if (!(s > 0 && Number.isFinite(s))) return;
  const { view, bounds } = frame;
  const toX = (x: number) => width / 2 + (x - view.cx) * s;
  const toY = (y: number) => height / 2 - (y - view.cy) * s;

  if (source) {
    const [nx, ny] = frame.shape;
    const { dx, dy } = bounds;
    // µm at the canvas edges → the source columns and rows (row 0 = largest y) in view.
    const left = view.cx - width / 2 / s;
    const right = view.cx + width / 2 / s;
    const top = view.cy + height / 2 / s;
    const bottom = view.cy - height / 2 / s;
    const c0 = Math.max(0, Math.floor((left - bounds.xMin) / dx));
    const c1 = Math.min(nx, Math.ceil((right - bounds.xMin) / dx));
    const r0 = Math.max(0, Math.floor((bounds.yMax - top) / dy));
    const r1 = Math.min(ny, Math.ceil((bounds.yMax - bottom) / dy));
    if (c1 > c0 && r1 > r0) {
      ctx.imageSmoothingEnabled = false; // one crisp block per node
      ctx.drawImage(
        source,
        c0,
        r0,
        c1 - c0,
        r1 - r0,
        toX(bounds.xMin + c0 * dx),
        toY(bounds.yMax - r0 * dy),
        (c1 - c0) * dx * s,
        (r1 - r0) * dy * s,
      );
    }
  }

  if (outlines.length > 0) {
    const lineWidth = Math.max(1, Math.round(ratio)); // 1 CSS px
    const snap = (v: number) => Math.round(v) + (lineWidth % 2 === 1 ? 0.5 : 0);
    ctx.globalAlpha = OUTLINE_ALPHA;
    ctx.strokeStyle = outlineColour;
    ctx.lineWidth = lineWidth;
    ctx.beginPath(); // one path, so overlapping edges are not darker
    for (const box of outlines) {
      const x0 = snap(toX(Math.min(box.x0, box.x1)));
      const x1 = snap(toX(Math.max(box.x0, box.x1)));
      const y0 = snap(toY(Math.max(box.y0, box.y1)));
      const y1 = snap(toY(Math.min(box.y0, box.y1)));
      ctx.rect(x0, y0, x1 - x0, y1 - y0);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }
}

/** The coloured field at one pixel per node, ready for drawImage. Null when empty. */
function fieldImage(data: Float32Array, shape: Shape, options: RenderOptions) {
  const [nx, ny] = shape;
  if (nx * ny === 0) return null;
  const canvas = document.createElement("canvas");
  canvas.width = nx;
  canvas.height = ny;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.putImageData(renderToImageData(data, shape, options, ctx.createImageData(nx, ny)), 0, 0);
  return canvas;
}

/**
 * A float32 field on a 2D canvas (ui-ux-spec §5.4): float32 → colormap LUT → ImageData,
 * drawn crisp, aspect kept, centred. Wheel zooms about the cursor, drag pans,
 * double-click resets; hover reports the nearest node. It redraws when its props or
 * the view change, never in a loop, so a live run redraws once per snapshot.
 */
export function FieldCanvas({
  label,
  data,
  shape,
  extent,
  colormap,
  scale = "linear",
  symmetric = false,
  range,
  outlines = NO_OUTLINES,
  onHover,
  className,
  ref,
}: FieldCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number; frame: Frame } | null>(
    null,
  );
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [view, setView] = useState<View | null>(null);
  const [themeChanges, setThemeChanges] = useState(0);

  const [nx, ny] = shape;
  const [x0, x1, y0, y1] = extent;
  const low = range?.[0];
  const high = range?.[1];
  const key = `${nx} ${ny} ${x0} ${x1} ${y0} ${y1}`;

  const geometry = useMemo(() => {
    const ownShape: Shape = [nx, ny];
    return { shape: ownShape, bounds: fieldBounds(ownShape, [x0, x1, y0, y1]) };
  }, [nx, ny, x0, x1, y0, y1]);

  const source = useMemo(
    () =>
      fieldImage(data, [nx, ny], {
        colormap,
        scale,
        symmetric,
        range: low !== undefined && high !== undefined ? [low, high] : undefined,
      }),
    [data, nx, ny, colormap, scale, symmetric, low, high],
  );

  const frame = useMemo<Frame>(
    () => ({
      width: size.width,
      height: size.height,
      shape: geometry.shape,
      bounds: geometry.bounds,
      view: view && view.key === key ? view : fitView(key, geometry.bounds),
    }),
    [size, geometry, view, key],
  );

  // The canvas's CSS size; ResizeObserver also reports once when observation starts.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[entries.length - 1]?.contentRect;
      if (!box) return;
      setSize((old) =>
        old.width === box.width && old.height === box.height
          ? old
          : { width: box.width, height: box.height },
      );
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  // Outlines use the text colour; redraw when the theme (or the OS theme) changes.
  useEffect(() => {
    const bump = () => setThemeChanges((n) => n + 1);
    const observer = new MutationObserver(bump);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    const media = window.matchMedia("(prefers-color-scheme: light)");
    media.addEventListener("change", bump);
    return () => {
      observer.disconnect();
      media.removeEventListener("change", bump);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || frame.width <= 0 || frame.height <= 0) return;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.round(frame.width * ratio);
    const height = Math.round(frame.height * ratio);
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const text = cssColour(canvas, "--et-text", FALLBACK_TEXT);
    paint(ctx, frame, ratio, source, outlines, text, null);
  }, [frame, source, outlines, themeChanges]);

  function hoverAt(at: Frame, px: number, py: number): FieldSample | null {
    if (!(at.width > 0 && at.height > 0)) return null;
    const [x, y] = toUm(at, px, py);
    const hit = sampleAt(data, at.shape, extent, x, y);
    if (!hit) return null;
    const [nodeX, nodeY] = nodePosition(at.shape, extent, hit.i, hit.j);
    return { x: nodeX, y: nodeY, value: hit.value, i: hit.i, j: hit.j };
  }

  // React's onWheel is passive, so it cannot stop the page from scrolling.
  const handleWheel = useEffectEvent((event: WheelEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    event.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const lines = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.height : 1;
    const factor = Math.exp(-event.deltaY * lines * WHEEL_ZOOM);
    setView((old) => {
      const at: Frame = {
        ...frame,
        width: rect.width,
        height: rect.height,
        view: old && old.key === key ? old : fitView(key, frame.bounds),
      };
      return zoomAbout(at, px, py, factor);
    });
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const listener = (event: WheelEvent) => handleWheel(event);
    canvas.addEventListener("wheel", listener, { passive: false });
    return () => canvas.removeEventListener("wheel", listener);
  }, []);

  function handlePointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      frame: liveFrame(event.currentTarget, frame),
    };
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    let at = liveFrame(canvas, frame);
    const drag = dragRef.current;
    if (drag && drag.pointerId === event.pointerId) {
      const s = pxPerUm(drag.frame);
      const panned: View = {
        ...drag.frame.view,
        cx: drag.frame.view.cx - (event.clientX - drag.x) / s,
        cy: drag.frame.view.cy + (event.clientY - drag.y) / s,
      };
      setView(panned);
      at = { ...at, view: panned };
    }
    onHover?.(hoverAt(at, event.clientX - rect.left, event.clientY - rect.top));
  }

  function endDrag(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  useImperativeHandle(
    ref,
    () => ({
      resetView: () => setView(null),
      toPng: (pngScale = 2) => {
        const canvas = canvasRef.current;
        if (!canvas) return Promise.reject(new Error("FieldCanvas.toPng: not mounted"));
        if (!(pngScale > 0 && Number.isFinite(pngScale))) {
          return Promise.reject(new RangeError(`FieldCanvas.toPng: scale ${pngScale} is not > 0`));
        }
        const at = liveFrame(canvas, frame);
        if (!(at.width > 0 && at.height > 0)) {
          return Promise.reject(new Error("FieldCanvas.toPng: the canvas has no size yet"));
        }
        const out = document.createElement("canvas");
        out.width = Math.round(at.width * pngScale);
        out.height = Math.round(at.height * pngScale);
        const ctx = out.getContext("2d");
        if (!ctx) return Promise.reject(new Error("FieldCanvas.toPng: no 2D canvas context"));
        paint(
          ctx,
          at,
          pngScale,
          source,
          outlines,
          cssColour(canvas, "--et-text", FALLBACK_TEXT),
          cssColour(canvas, "--et-bg", FALLBACK_BG),
        );
        return new Promise<Blob>((resolve, reject) => {
          out.toBlob((blob) => {
            if (blob) resolve(blob);
            else reject(new Error("FieldCanvas.toPng: the browser produced no PNG"));
          }, "image/png");
        });
      },
    }),
    [frame, source, outlines],
  );

  return (
    <div className={cx("relative min-h-0 min-w-0 overflow-hidden bg-bg", className)}>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={label}
        className="absolute inset-0 block h-full w-full cursor-crosshair touch-none select-none"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={() => {
          dragRef.current = null;
        }}
        onPointerLeave={() => onHover?.(null)}
        onDoubleClick={() => setView(null)}
      />
    </div>
  );
}
