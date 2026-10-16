// The field-rendering layer: binary frames (plan-u1 §13.1), colormaps, float32 → RGBA.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { NetworkError, ServerError, SessionEndedError } from "../api/client";
import { BinaryFormatError, decodeArray, fetchArray, type FieldHeader } from "./binary";
import { COLORMAP_SIZE, COLORMAPS, RdBu, viridis } from "./colormaps";
import {
  colormapEntry,
  dataRange,
  fieldBounds,
  formatTick,
  log2Float32,
  renderToImageData,
  resolveRange,
  sampleAt,
  type RenderOptions,
} from "./render";

// jsdom has no ImageData; a minimal one with the same fields stands in.
class ImageDataStub {
  readonly data: Uint8ClampedArray;
  readonly colorSpace = "srgb";
  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.data = new Uint8ClampedArray(width * height * 4);
  }
}

beforeAll(() => {
  if (typeof globalThis.ImageData === "undefined") vi.stubGlobal("ImageData", ImageDataStub);
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (typeof globalThis.ImageData === "undefined") vi.stubGlobal("ImageData", ImageDataStub);
});

/** A frame built by hand, byte by byte, as the server writes it. */
function frameOf(header: unknown, values: readonly number[], extraBytes = 0): ArrayBuffer {
  const json = new TextEncoder().encode(JSON.stringify(header));
  const start = Math.ceil((4 + json.length) / 4) * 4;
  const buffer = new ArrayBuffer(start + 4 * values.length + extraBytes);
  const view = new DataView(buffer);
  view.setUint32(0, json.length, true);
  new Uint8Array(buffer, 4, json.length).set(json);
  values.forEach((v, k) => view.setFloat32(start + 4 * k, v, true));
  return buffer;
}

/** A frame whose header bytes are given verbatim (for broken headers). */
function rawFrame(headerBytes: Uint8Array, dataBytes = 0): ArrayBuffer {
  const start = Math.ceil((4 + headerBytes.length) / 4) * 4;
  const buffer = new ArrayBuffer(start + dataBytes);
  new DataView(buffer).setUint32(0, headerBytes.length, true);
  new Uint8Array(buffer, 4, headerBytes.length).set(headerBytes);
  return buffer;
}

const HEADER: FieldHeader = {
  kind: "field",
  component: "Hz",
  quantity: "real",
  unit: "V·s/m", // "·" is two UTF-8 bytes: N counts bytes, not characters
  wavelength_um: 1.55,
  shape: [3, 2],
  extent: [-1, 1, 0, 0.5],
  min: 0,
  max: 5,
};
const VALUES = [0, 1, 2, 3, 4, 5];

function rgbaAt(image: ImageData, column: number, row: number): number[] {
  const k = 4 * (row * image.width + column);
  return Array.from(image.data.slice(k, k + 4));
}

function opaque(rgb: [number, number, number]): number[] {
  return [...rgb, 255];
}

const LINEAR_VIRIDIS: RenderOptions = { colormap: "viridis", scale: "linear", symmetric: false };

describe("decodeArray", () => {
  it("round-trips a hand-built frame into the header and a zero-copy view", () => {
    const buffer = frameOf(HEADER, VALUES);
    const { header, data } = decodeArray<FieldHeader>(buffer);
    expect(header).toEqual(HEADER);
    expect(Array.from(data)).toEqual(VALUES);
    expect(data.buffer).toBe(buffer); // a view, not a copy
    expect(data.byteOffset % 4).toBe(0);
    const headerBytes = new TextEncoder().encode(JSON.stringify(HEADER)).length;
    expect(headerBytes).toBeGreaterThan(JSON.stringify(HEADER).length);
    expect(data.byteOffset).toBe(Math.ceil((4 + headerBytes) / 4) * 4);
  });

  it("accepts an empty array", () => {
    const { data } = decodeArray(frameOf({ ...HEADER, shape: [0, 4] }, []));
    expect(data.length).toBe(0);
  });

  it.each([
    ["is shorter than the length word", new ArrayBuffer(3), /too short/],
    [
      "has a header length past the end",
      (() => {
        const buffer = new ArrayBuffer(8);
        new DataView(buffer).setUint32(0, 100, true);
        return buffer;
      })(),
      /runs past the end/,
    ],
    ["has a header that is not JSON", rawFrame(new TextEncoder().encode("{shape: [1, 1]")), /JSON/],
    ["has a header that is not UTF-8", rawFrame(new Uint8Array([0x7b, 0xff, 0x7d])), /UTF-8/],
    ["has a JSON array for a header", frameOf([1, 2], []), /not a JSON object/],
    ["has no shape", frameOf({ kind: "field" }, []), /shape/],
    ["has a fractional shape", frameOf({ shape: [1.5, 2] }, [0, 0, 0]), /shape/],
    ["has a bad extent", frameOf({ shape: [1, 1], extent: [0, 1] }, [0]), /extent/],
    ["is misaligned (data not whole float32s)", frameOf(HEADER, VALUES, 2), /whole number of float32/],
    ["is short of n_x·n_y values", frameOf(HEADER, VALUES.slice(0, 5)), /5 float32 values .* needs 6/],
    ["has more than n_x·n_y values", frameOf(HEADER, [...VALUES, 6]), /7 float32 values .* needs 6/],
  ])("throws BinaryFormatError when the frame %s", (_, buffer, message) => {
    expect(() => decodeArray(buffer)).toThrow(BinaryFormatError);
    expect(() => decodeArray(buffer)).toThrow(message);
  });

  it("throws when the header's padding is cut off", () => {
    // N = 5 → the data would start at byte 12, but the frame ends at byte 9.
    const json = new TextEncoder().encode('{"a":');
    expect(json.length).toBe(5);
    const buffer = new ArrayBuffer(4 + 5);
    new DataView(buffer).setUint32(0, 5, true);
    new Uint8Array(buffer, 4).set(json);
    expect(() => decodeArray(buffer)).toThrow(BinaryFormatError);
  });

  it("names itself in the error", () => {
    try {
      decodeArray(new ArrayBuffer(0));
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(BinaryFormatError);
      expect((error as Error).name).toBe("BinaryFormatError");
      expect((error as Error).message).toMatch(/^Binary array frame: /);
    }
  });
});

describe("fetchArray", () => {
  it("passes the caller's init through and decodes the body", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(frameOf(HEADER, VALUES), {
          status: 200,
          headers: { "Content-Type": "application/octet-stream" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const init = { headers: { "X-Etalon-Token": "t" } };
    const { header, data } = await fetchArray<FieldHeader>("/api/results/r/fields/m", init);
    expect(fetchMock).toHaveBeenCalledWith("/api/results/r/fields/m", init);
    expect(header.quantity).toBe("real");
    expect(Array.from(data)).toEqual(VALUES);
  });

  it("throws ServerError with the JSON body on a non-2xx answer", async () => {
    const body = { code: "monitor_not_found", message: "no monitor m" };
    vi.stubGlobal("fetch", async () => Response.json(body, { status: 404 }));
    const error = await fetchArray("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ServerError);
    expect((error as ServerError).status).toBe(404);
    expect((error as ServerError).code).toBe("monitor_not_found");
  });

  it("throws SessionEndedError on 401 and NetworkError when unreachable", async () => {
    vi.stubGlobal("fetch", async () => new Response(null, { status: 401 }));
    await expect(fetchArray("/x")).rejects.toBeInstanceOf(SessionEndedError);
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(fetchArray("/x")).rejects.toBeInstanceOf(NetworkError);
  });

  it("throws BinaryFormatError on a 200 that is not a frame", async () => {
    vi.stubGlobal("fetch", async () => new Response(new Uint8Array([1, 2])));
    await expect(fetchArray("/x")).rejects.toBeInstanceOf(BinaryFormatError);
  });
});

describe("colormaps", () => {
  it("are 256 RGB triples each", () => {
    expect(COLORMAP_SIZE).toBe(256);
    for (const table of Object.values(COLORMAPS)) expect(table.length).toBe(256 * 3);
  });

  it("match matplotlib's viridis endpoints", () => {
    expect(Array.from(viridis.slice(0, 3))).toEqual([68, 1, 84]);
    expect(Array.from(viridis.slice(765, 768))).toEqual([253, 231, 37]);
  });

  it("run RdBu from blue (negative) through white to red (positive)", () => {
    const [r0, , b0] = colormapEntry("RdBu", 0);
    const [r255, , b255] = colormapEntry("RdBu", 255);
    expect(b0).toBeGreaterThan(r0);
    expect(r255).toBeGreaterThan(b255);
    for (const channel of colormapEntry("RdBu", 128)) expect(channel).toBeGreaterThan(240);
    expect(Array.from(RdBu.slice(0, 3))).toEqual(colormapEntry("RdBu", 0));
  });
});

describe("dataRange and resolveRange", () => {
  it("ignore NaN and ±Inf", () => {
    const data = new Float32Array([NaN, -2, 3, Infinity, -Infinity]);
    expect(dataRange(data, "linear")).toEqual([-2, 3]);
    expect(dataRange(new Float32Array([NaN, NaN]), "linear")).toEqual([0, 0]);
  });

  it("give the positive minimum for log", () => {
    const data = new Float32Array([0, -1, 0.25, 5]);
    expect(dataRange(data, "log")).toEqual([0.25, 5]);
    expect(dataRange(new Float32Array([0, -1]), "log")).toEqual([0, 0]);
  });

  it("make the range symmetric, honour an explicit one, and widen a constant field", () => {
    const data = new Float32Array([-1, 0.5, 3]);
    expect(resolveRange(data, { scale: "linear", symmetric: true })).toEqual([-3, 3]);
    expect(resolveRange(data, { scale: "linear", symmetric: false })).toEqual([-1, 3]);
    expect(resolveRange(data, { scale: "linear", symmetric: false, range: [0, 2] })).toEqual([0, 2]);
    expect(resolveRange(data, { scale: "linear", symmetric: true, range: [-1, 2] })).toEqual([-2, 2]);
    expect(resolveRange(new Float32Array([4, 4]), { scale: "linear", symmetric: false })).toEqual([
      0, 8,
    ]);
    expect(resolveRange(new Float32Array([0, 0]), { scale: "linear", symmetric: true })).toEqual([
      -1, 1,
    ]);
    expect(resolveRange(new Float32Array([2, 2]), { scale: "log", symmetric: false })).toEqual([
      0.2, 20,
    ]);
    // A non-positive log bound falls back to the data's positive range.
    expect(
      resolveRange(new Float32Array([0.5, 8]), { scale: "log", symmetric: false, range: [0, 4] }),
    ).toEqual([0.5, 4]);
  });
});

describe("renderToImageData", () => {
  it("puts x along columns and the largest y in row 0", () => {
    // shape [3, 2]: data[i * 2 + j] = node (x_i, y_j); one hot node at x max, y max.
    const data = new Float32Array(6);
    data[2 * 2 + 1] = 1;
    const image = renderToImageData(data, [3, 2], LINEAR_VIRIDIS);
    expect([image.width, image.height]).toEqual([3, 2]);
    expect(rgbaAt(image, 2, 0)).toEqual(opaque(colormapEntry("viridis", 255))); // top-right
    for (const [column, row] of [[0, 0], [1, 0], [0, 1], [1, 1], [2, 1]] as const) {
      expect(rgbaAt(image, column, row)).toEqual(opaque(colormapEntry("viridis", 0)));
    }
  });

  it("places every node at (column i, row n_y - 1 - j)", () => {
    const [nx, ny] = [3, 2];
    const data = Float32Array.from({ length: nx * ny }, (_, k) => k); // k = i * ny + j
    // range [0, 8]: 32 entries per unit, exact in floating point.
    const image = renderToImageData(data, [nx, ny], { ...LINEAR_VIRIDIS, range: [0, 8] });
    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        const index = 32 * (i * ny + j);
        expect(rgbaAt(image, i, ny - 1 - j)).toEqual(opaque(colormapEntry("viridis", index)));
      }
    }
  });

  it("maps 0 to RdBu's centre with a symmetric range", () => {
    const data = new Float32Array([-1, 0, 2]); // symmetric → [-2, 2]
    const image = renderToImageData(data, [3, 1], {
      colormap: "RdBu",
      scale: "linear",
      symmetric: true,
    });
    expect(rgbaAt(image, 0, 0)).toEqual(opaque(colormapEntry("RdBu", 64)));
    expect(rgbaAt(image, 1, 0)).toEqual(opaque(colormapEntry("RdBu", 128)));
    expect(rgbaAt(image, 2, 0)).toEqual(opaque(colormapEntry("RdBu", 255)));
  });

  it("spaces a log scale by decades and gives v ≤ 0 the lowest colour", () => {
    const data = new Float32Array([1, 10, 100, 1000, 0, -5]);
    const image = renderToImageData(data, [6, 1], {
      colormap: "viridis",
      scale: "log",
      symmetric: false,
    });
    const expected = [0, 85, 170, 255, 0, 0]; // floor(log10(v) / 3 * 256)
    expected.forEach((index, column) => {
      expect(rgbaAt(image, column, 0)).toEqual(opaque(colormapEntry("viridis", index)));
    });
  });

  it("bins a log scale as the exact formula does, away from bin edges", () => {
    // 4096 values spread evenly in log over 1e-6 … 1.
    const n = 4096;
    const data = Float32Array.from({ length: n }, (_, k) => 10 ** (-6 + (6 * (k + 0.37)) / n));
    const image = renderToImageData(data, [n, 1], {
      colormap: "RdBu",
      scale: "log",
      symmetric: false,
      range: [1e-6, 1],
    });
    let checked = 0;
    for (let k = 0; k < n; k++) {
      const t = ((Math.log10(data[k] as number) + 6) / 6) * 256;
      if (Math.abs(t - Math.round(t)) < 1e-4) continue; // on an edge either side is right
      const index = Math.min(255, Math.max(0, Math.floor(t)));
      expect(rgbaAt(image, k, 0)).toEqual(opaque(colormapEntry("RdBu", index)));
      checked++;
    }
    expect(checked).toBeGreaterThan(4000);
  });

  it("clamps values outside an explicit range", () => {
    const data = new Float32Array([-10, 0.5, 10]);
    const image = renderToImageData(data, [3, 1], { ...LINEAR_VIRIDIS, range: [0, 1] });
    expect(rgbaAt(image, 0, 0)).toEqual(opaque(colormapEntry("viridis", 0)));
    expect(rgbaAt(image, 1, 0)).toEqual(opaque(colormapEntry("viridis", 128)));
    expect(rgbaAt(image, 2, 0)).toEqual(opaque(colormapEntry("viridis", 255)));
  });

  /** NaN with the sign bit set, as x86 produces for 0/0 (NumPy's nan has it clear). */
  function negativeNaN(): number {
    const cell = new Float32Array(1);
    new Uint32Array(cell.buffer)[0] = 0xffc00000;
    return cell[0] as number;
  }

  it("leaves NaN pixels transparent and clamps ±Inf to the end colours", () => {
    const data = new Float32Array([NaN, 1, Infinity, 2, -Infinity, negativeNaN()]);
    expect(Number.isNaN(data[5])).toBe(true);
    const image = renderToImageData(data, [6, 1], LINEAR_VIRIDIS); // range [1, 2]
    expect(rgbaAt(image, 0, 0)).toEqual([0, 0, 0, 0]);
    expect(rgbaAt(image, 1, 0)).toEqual(opaque(colormapEntry("viridis", 0)));
    expect(rgbaAt(image, 2, 0)).toEqual(opaque(colormapEntry("viridis", 255)));
    expect(rgbaAt(image, 3, 0)).toEqual(opaque(colormapEntry("viridis", 255)));
    expect(rgbaAt(image, 4, 0)).toEqual(opaque(colormapEntry("viridis", 0)));
    expect(rgbaAt(image, 5, 0)).toEqual([0, 0, 0, 0]);
  });

  it("does the same on a log scale, with v ≤ 0 at the lowest colour", () => {
    const data = new Float32Array([NaN, 1, Infinity, 100, -Infinity, negativeNaN(), -0, 1e-42]);
    const image = renderToImageData(data, [8, 1], {
      colormap: "viridis",
      scale: "log",
      symmetric: false,
      range: [1, 100],
    });
    const lowest = opaque(colormapEntry("viridis", 0));
    const highest = opaque(colormapEntry("viridis", 255));
    const expected = [[0, 0, 0, 0], lowest, highest, highest, lowest, [0, 0, 0, 0], lowest, lowest];
    expected.forEach((rgba, column) => expect(rgbaAt(image, column, 0)).toEqual(rgba));
  });

  it("fills a given target and rejects a shape that does not fit", () => {
    const target = new ImageData(2, 2);
    const data = new Float32Array([0, 1, 2, 3]);
    expect(renderToImageData(data, [2, 2], LINEAR_VIRIDIS, target)).toBe(target);
    expect(() => renderToImageData(data, [3, 2], LINEAR_VIRIDIS)).toThrow(RangeError);
    expect(() => renderToImageData(data, [4, 1], LINEAR_VIRIDIS, target)).toThrow(RangeError);
  });
});

describe("log2Float32", () => {
  it("matches Math.log2 to 5e-8 for normal and subnormal float32 values", () => {
    const values = Float32Array.from({ length: 20000 }, (_, k) => 10 ** (-44 + (82 * k) / 20000));
    const bits = new Uint32Array(values.buffer);
    let subnormals = 0;
    for (let k = 0; k < values.length; k++) {
      const v = values[k] as number;
      if (!(v > 0)) continue;
      if (v < 1.1754943508222875e-38) subnormals++;
      expect(Math.abs(log2Float32(bits[k] as number) - Math.log2(v))).toBeLessThan(5e-8);
    }
    expect(subnormals).toBeGreaterThan(100);
  });
});

describe("sampleAt and fieldBounds", () => {
  // Nodes at x = 0, 1, 2 and y = 10, 11 (µm); data[i * 2 + j] = 10 i + j.
  const data = new Float32Array([0, 1, 10, 11, 20, 21]);
  const shape = [3, 2] as const;
  const extent = [0, 2, 10, 11] as const;

  it("returns the nearest node", () => {
    expect(sampleAt(data, shape, extent, 1.2, 10.9)).toEqual({ value: 11, i: 1, j: 1 });
    expect(sampleAt(data, shape, extent, -0.49, 9.51)).toEqual({ value: 0, i: 0, j: 0 });
    expect(sampleAt(data, shape, extent, 2.5, 11.5)).toEqual({ value: 21, i: 2, j: 1 });
  });

  it("is null more than half a cell outside the nodes", () => {
    expect(sampleAt(data, shape, extent, -0.6, 10)).toBeNull();
    expect(sampleAt(data, shape, extent, 1, 11.6)).toBeNull();
    expect(sampleAt(data, shape, extent, Number.NaN, 10)).toBeNull();
  });

  it("puts the image edges half a cell beyond the first and last nodes", () => {
    expect(fieldBounds(shape, extent)).toEqual({
      xMin: -0.5,
      xMax: 2.5,
      yMin: 9.5,
      yMax: 11.5,
      dx: 1,
      dy: 1,
    });
    // One node along y borrows the x spacing.
    expect(fieldBounds([3, 1], [0, 1, 5, 5])).toMatchObject({ dy: 0.5, yMin: 4.75, yMax: 5.25 });
  });
});

describe("formatTick", () => {
  it.each([
    [0, "0"],
    [-0, "0"],
    [0.5, "0.5"],
    [12, "12"],
    [1234.5, "1230"],
    [-0.0042, "-0.0042"],
    [1.234e-5, "1.23e-5"],
    [1e-5, "1e-5"],
    [-3e6, "-3e6"],
    [6.02e23, "6.02e23"],
  ])("%s → %s", (value, text) => {
    expect(formatTick(value)).toBe(text);
  });
});
