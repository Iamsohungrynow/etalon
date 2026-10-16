// FieldCanvas and ColorScale. jsdom has no 2D canvas, so getContext returns a recording
// fake; layout is a fixed 400 × 200 px box (ResizeObserver and getBoundingClientRect).
import { act, fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { colormapEntry } from "../field/render";
import { ColorScale } from "./ColorScale";
import { FieldCanvas, type FieldCanvasHandle, type FieldOutline } from "./FieldCanvas";

const WIDTH = 400;
const HEIGHT = 200;

/** The parts of CanvasRenderingContext2D the components use, recorded. */
function fakeContext(canvas: HTMLCanvasElement) {
  return {
    canvas,
    imageSmoothingEnabled: true,
    globalAlpha: 1,
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    setTransform: vi.fn(),
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    drawImage: vi.fn(),
    putImageData: vi.fn(),
    beginPath: vi.fn(),
    rect: vi.fn(),
    stroke: vi.fn(),
    createImageData: (width: number, height: number) => ({
      width,
      height,
      colorSpace: "srgb",
      data: new Uint8ClampedArray(width * height * 4),
    }),
  };
}
type FakeContext = ReturnType<typeof fakeContext>;

let contexts: Map<HTMLCanvasElement, FakeContext>;

function contextOf(canvas: HTMLElement): FakeContext {
  const ctx = contexts.get(canvas as HTMLCanvasElement);
  if (!ctx) throw new Error("no 2D context was requested for this canvas");
  return ctx;
}

/** Reports the fixed box as soon as an element is observed, as browsers do. */
class FixedResizeObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}
  observe(target: Element): void {
    const entry = { target, contentRect: { width: WIDTH, height: HEIGHT } };
    this.callback([entry as unknown as ResizeObserverEntry], this as unknown as ResizeObserver);
  }
  unobserve(): void {}
  disconnect(): void {}
}

beforeEach(() => {
  contexts = new Map();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(function (
    this: HTMLCanvasElement,
  ) {
    let ctx = contexts.get(this);
    if (!ctx) {
      ctx = fakeContext(this);
      contexts.set(this, ctx);
    }
    return ctx as unknown as CanvasRenderingContext2D;
  } as unknown as HTMLCanvasElement["getContext"]);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
    callback(new Blob(["png"], { type: "image/png" }));
  });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    width: WIDTH,
    height: HEIGHT,
    right: WIDTH,
    bottom: HEIGHT,
    toJSON: () => ({}),
  });
  vi.stubGlobal("ResizeObserver", FixedResizeObserver);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// Nodes x = 0…4, y = 0…2 (µm, 1 µm apart); data[i * 3 + j] = 10 i + j. The image
// spans 5 × 3 µm, so it fits the 400 × 200 box at 200/3 px per µm, centred on (2, 1).
const SHAPE = [5, 3] as const;
const EXTENT = [0, 4, 0, 2] as const;
const DATA = Float32Array.from({ length: 15 }, (_, k) => 10 * Math.floor(k / 3) + (k % 3));
const PX_PER_UM = HEIGHT / 3;
const OUTLINES: FieldOutline[] = [{ x0: 1, x1: 3, y0: 0, y1: 2 }];

/** Client px of the point (x, y) µm at the initial (fitted) view. */
function at(x: number, y: number) {
  return { clientX: WIDTH / 2 + (x - 2) * PX_PER_UM, clientY: HEIGHT / 2 - (y - 1) * PX_PER_UM };
}

function renderField(onHover = vi.fn(), ref = createRef<FieldCanvasHandle>()) {
  const view = render(
    <FieldCanvas
      ref={ref}
      label="Hz, real part"
      data={DATA}
      shape={SHAPE}
      extent={EXTENT}
      colormap="RdBu"
      symmetric
      outlines={OUTLINES}
      onHover={onHover}
      className="h-96"
    />,
  );
  const canvas = screen.getByRole("img", { name: "Hz, real part" });
  return { ...view, canvas, onHover, ref };
}

describe("FieldCanvas", () => {
  it("is an image named by its label, crosshair over the canvas only", () => {
    const { canvas } = renderField();
    expect(canvas.tagName).toBe("CANVAS");
    expect(canvas).toHaveClass("cursor-crosshair");
    expect(canvas.parentElement).not.toHaveClass("cursor-crosshair");
    expect(canvas.parentElement).toHaveClass("h-96", "bg-bg");
  });

  it("draws the whole field crisp, centred with its aspect kept, and the outlines", () => {
    const { canvas } = renderField();
    const ctx = contextOf(canvas);
    expect([(canvas as HTMLCanvasElement).width, (canvas as HTMLCanvasElement).height]).toEqual([
      WIDTH,
      HEIGHT,
    ]);
    expect(ctx.imageSmoothingEnabled).toBe(false);
    expect(ctx.drawImage).toHaveBeenCalledTimes(1);
    const [source, sx, sy, sw, sh, dx, dy, dw, dh] = ctx.drawImage.mock.calls[0] as [
      HTMLCanvasElement,
      ...number[],
    ];
    expect([source.width, source.height]).toEqual([5, 3]); // one pixel per node
    expect([sx, sy, sw, sh]).toEqual([0, 0, 5, 3]);
    expect(dx).toBeCloseTo(WIDTH / 2 - 2.5 * PX_PER_UM);
    expect(dy).toBeCloseTo(0);
    expect(dw).toBeCloseTo(5 * PX_PER_UM); // equal µm per pixel in x and y
    expect(dh).toBeCloseTo(3 * PX_PER_UM);
    // The structure box x 1…3, y 0…2 µm, snapped to the pixel grid.
    expect(ctx.rect).toHaveBeenCalledWith(133.5, 33.5, 134, 134);
    expect(ctx.stroke).toHaveBeenCalledTimes(1);
    expect(ctx.lineWidth).toBe(1);
  });

  it("colours the source with the colormap (symmetric RdBu: 0 is the centre)", () => {
    const { canvas } = renderField();
    const [source] = contextOf(canvas).drawImage.mock.calls[0] as [HTMLCanvasElement];
    const [image] = contextOf(source).putImageData.mock.calls[0] as [ImageData];
    // Node (0, 0) is 0 → centre colour; it sits at the bottom-left pixel (row n_y - 1).
    const k = 4 * (2 * 5 + 0);
    expect(Array.from(image.data.slice(k, k + 3))).toEqual(colormapEntry("RdBu", 128));
  });

  it("does not redraw on a re-render with the same props", () => {
    const { canvas, rerender, onHover, ref } = renderField();
    const ctx = contextOf(canvas);
    const props = {
      ref,
      label: "Hz, real part",
      data: DATA,
      shape: [5, 3] as const,
      extent: [0, 4, 0, 2] as const,
      colormap: "RdBu" as const,
      symmetric: true,
      outlines: OUTLINES,
      onHover,
      className: "h-96",
    };
    rerender(<FieldCanvas {...props} />);
    expect(ctx.drawImage).toHaveBeenCalledTimes(1);
    rerender(<FieldCanvas {...props} colormap="viridis" symmetric={false} />);
    expect(ctx.drawImage).toHaveBeenCalledTimes(2);
  });

  it("reports the nearest node in µm on hover, and null outside or on leave", () => {
    const { canvas, onHover } = renderField();
    fireEvent.pointerMove(canvas, at(3.2, 1.9));
    expect(onHover).toHaveBeenLastCalledWith({ x: 3, y: 2, value: 32, i: 3, j: 2 });
    fireEvent.pointerMove(canvas, at(0, 0));
    expect(onHover).toHaveBeenLastCalledWith({ x: 0, y: 0, value: 0, i: 0, j: 0 });
    fireEvent.pointerMove(canvas, at(-0.8, 1)); // in the margin, beyond the half cell
    expect(onHover).toHaveBeenLastCalledWith(null);
    fireEvent.pointerMove(canvas, at(2, 1));
    fireEvent.pointerLeave(canvas);
    expect(onHover).toHaveBeenLastCalledWith(null);
  });

  it("zooms about the cursor with the wheel and stops the page scrolling", () => {
    const { canvas, onHover } = renderField();
    const anchor = at(3, 2);
    const notCancelled = fireEvent.wheel(canvas, { ...anchor, deltaY: -100 });
    expect(notCancelled).toBe(false); // preventDefault was called
    fireEvent.pointerMove(canvas, anchor);
    expect(onHover).toHaveBeenLastCalledWith(expect.objectContaining({ i: 3, j: 2 }));
    // Zoomed in, the margin point at x = -0.8 µm now shows the field's left column.
    fireEvent.pointerMove(canvas, at(-0.8, 1));
    expect(onHover).toHaveBeenLastCalledWith(expect.objectContaining({ i: 0 }));
  });

  it("pans by dragging and resets on double-click", () => {
    const { canvas, onHover } = renderField();
    fireEvent.pointerDown(canvas, { ...at(2, 1), button: 0, pointerId: 1 });
    fireEvent.pointerMove(canvas, { ...at(3, 1), pointerId: 1 });
    // The node under the cursor travels with it.
    expect(onHover).toHaveBeenLastCalledWith(expect.objectContaining({ x: 2, y: 1 }));
    fireEvent.pointerUp(canvas, { ...at(3, 1), pointerId: 1 });
    fireEvent.pointerMove(canvas, at(2, 1));
    expect(onHover).toHaveBeenLastCalledWith(expect.objectContaining({ x: 1, y: 1, value: 11 }));
    fireEvent.doubleClick(canvas);
    fireEvent.pointerMove(canvas, at(2, 1));
    expect(onHover).toHaveBeenLastCalledWith(expect.objectContaining({ x: 2, y: 1, value: 21 }));
  });

  it("exposes resetView and toPng through its ref", async () => {
    const { canvas, onHover, ref } = renderField();
    expect(typeof ref.current?.resetView).toBe("function");
    fireEvent.pointerDown(canvas, { ...at(2, 1), button: 0, pointerId: 1 });
    fireEvent.pointerMove(canvas, { ...at(3, 1), pointerId: 1 });
    fireEvent.pointerUp(canvas, { ...at(3, 1), pointerId: 1 });
    act(() => ref.current?.resetView());
    fireEvent.pointerMove(canvas, at(2, 1));
    expect(onHover).toHaveBeenLastCalledWith(expect.objectContaining({ x: 2, y: 1 }));

    const before = new Set(contexts.keys());
    const blob = await ref.current?.toPng(2);
    expect(blob?.type).toBe("image/png");
    const exported = [...contexts.entries()].find(([c]) => !before.has(c));
    expect(exported).toBeDefined();
    const [out, ctx] = exported as [HTMLCanvasElement, FakeContext];
    expect([out.width, out.height]).toEqual([2 * WIDTH, 2 * HEIGHT]);
    expect(ctx.fillRect).toHaveBeenCalledWith(0, 0, 2 * WIDTH, 2 * HEIGHT); // opaque bg
    expect(ctx.drawImage).toHaveBeenCalledTimes(1);
    expect(ctx.lineWidth).toBe(2); // 1 CSS px at 2×
    await expect(ref.current?.toPng(0)).rejects.toThrow(RangeError);
  });
});

describe("ColorScale", () => {
  it("draws the colormap bar and labels min, mid and max", () => {
    render(<ColorScale colormap="viridis" min={0} max={1} scale="linear" unit="V/m" label="|E|" />);
    const group = screen.getByRole("group", { name: "|E|" });
    expect(group).toHaveTextContent("0");
    expect(screen.getByText("0.5")).toBeInTheDocument();
    expect(screen.getByText("1 V/m")).toHaveAttribute("translate", "no");
    const bar = group.querySelector("canvas") as HTMLCanvasElement;
    expect(bar).toHaveAttribute("aria-hidden", "true");
    const [image] = contextOf(bar).putImageData.mock.calls[0] as [ImageData];
    expect(image.width).toBe(256);
    expect(Array.from(image.data.slice(0, 4))).toEqual([...colormapEntry("viridis", 0), 255]);
    expect(Array.from(image.data.slice(1020, 1024))).toEqual([
      ...colormapEntry("viridis", 255),
      255,
    ]);
  });

  it("puts the geometric mean in the middle of a log scale", () => {
    render(<ColorScale colormap="viridis" min={1e-4} max={1} scale="log" label="|E|²" />);
    expect(screen.getByText("0.01")).toBeInTheDocument();
    expect(screen.getByText("1e-4")).toBeInTheDocument();
  });
});
