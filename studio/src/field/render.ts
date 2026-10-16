/**
 * float32 field → colormap → ImageData, and the node geometry the canvas needs.
 *
 * Layout (docs/plan-u1.md §13.1): `shape = [n_x, n_y]` in C order, `data[i * n_y + j]`
 * is node (x_i, y_j); `extent = [x_first, x_last, y_first, y_last]` in µm, the first
 * and last nodes, uniform spacing, first < last. Each node is drawn as one pixel
 * centred on the node, so the image covers [x_first - dx/2, x_last + dx/2] in x.
 *
 * Image column = x index, image row 0 = the largest y (y points up, as in a plot).
 */
import { COLORMAP_SIZE, COLORMAPS, type ColormapName } from "./colormaps";

export type { ColormapName } from "./colormaps";
export type ScaleKind = "linear" | "log";
export type Shape = readonly [number, number];
export type Extent = readonly [number, number, number, number];

export interface RenderOptions {
  colormap: ColormapName;
  scale: ScaleKind;
  /** ±max|v| (linear only): 0 lands on the colormap's centre. Meant for RdBu. */
  symmetric: boolean;
  /** Colour limits [low, high]; the data's finite range when absent. */
  range?: readonly [number, number];
}

const TOP = COLORMAP_SIZE - 1;
const HALF = COLORMAP_SIZE / 2;

/**
 * Packed RGBA in the byte order of a Uint32Array view of ImageData, shifted by one:
 * slot 0 is transparent (for NaN), slots 1…256 are colormap entries 0…255.
 */
const packedLuts = new Map<ColormapName, Uint32Array>();

/** Byte order of the host; every browser Studio supports is little-endian. */
const LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

function packedLut(name: ColormapName): Uint32Array {
  let lut = packedLuts.get(name);
  if (lut) return lut;
  const rgb = COLORMAPS[name];
  lut = new Uint32Array(COLORMAP_SIZE + 1); // lut[0] = 0: transparent
  for (let k = 0; k < COLORMAP_SIZE; k++) {
    const r = rgb[3 * k] ?? 0;
    const g = rgb[3 * k + 1] ?? 0;
    const b = rgb[3 * k + 2] ?? 0;
    lut[k + 1] = LITTLE_ENDIAN
      ? ((255 << 24) | (b << 16) | (g << 8) | r) >>> 0
      : ((r << 24) | (g << 16) | (b << 8) | 255) >>> 0;
  }
  packedLuts.set(name, lut);
  return lut;
}

/** log2(1 + k / 2048), k = 0…2048: the mantissa part of log2Float32. */
const MANTISSA_LOG2 = Float64Array.from({ length: 2049 }, (_, k) => Math.log2(1 + k / 2048));

/**
 * log2 of a positive, finite float32 given its bit pattern (IEEE 754 binary32):
 * v = 2^(e - 127) · (1 + m / 2^23), so log2 v = e - 127 + log2(1 + m / 2^23), the last
 * term interpolated linearly in a 2048-entry table. |error| < 5e-8, under 1 % of a
 * colour bin for any log range wider than a factor of 1.001, and 1.5–2× faster than
 * Math.log per node. Subnormals (e = 0) are v = m · 2^-149, done with Math.log2.
 */
export function log2Float32(bits: number): number {
  const exponent = bits >>> 23; // the sign bit is 0 for a positive value
  const mantissa = bits & 0x7fffff;
  if (exponent === 0) return Math.log2(mantissa) - 149;
  const k = mantissa >>> 12; // top 11 of the 23 mantissa bits
  const a = MANTISSA_LOG2[k] as number;
  const b = MANTISSA_LOG2[k + 1] as number;
  return exponent - 127 + a + (b - a) * (mantissa & 0xfff) * (1 / 4096);
}

/** The colour of colormap entry `index` (0…255) as [r, g, b]. */
export function colormapEntry(name: ColormapName, index: number): [number, number, number] {
  const rgb = COLORMAPS[name];
  const k = 3 * Math.min(TOP, Math.max(0, Math.round(index)));
  return [rgb[k] ?? 0, rgb[k + 1] ?? 0, rgb[k + 2] ?? 0];
}

/**
 * Finite [min, max] of the data, ignoring NaN and ±Inf. For `log`, min is the smallest
 * positive value. [0, 0] when nothing qualifies (the header's own convention).
 */
export function dataRange(data: Float32Array, scale: ScaleKind): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  // Values must lie strictly between `floor` and +Inf; NaN fails every comparison.
  const floor = scale === "log" ? 0 : -Infinity;
  for (let n = 0; n < data.length; n++) {
    const v = data[n] as number;
    if (v > floor && v < Infinity) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  return min <= max ? [min, max] : [0, 0];
}

/**
 * The colour limits the image is drawn with, low < high (both > 0 for log), so a
 * ColorScale can show exactly what the canvas shows.
 *
 * - `range` given: used as is (symmetric widens it to ±max of its magnitudes; for log,
 *   a non-positive bound falls back to the data's positive range).
 * - `symmetric` (linear): [-m, m], m = max|v| over the finite data.
 * - otherwise: the data's finite range.
 *
 * A degenerate range (a constant field) is widened around its value v, so a constant
 * field draws in the colormap's centre colour: v ± |v| (± 1 for v = 0) when linear,
 * a factor of 10 either side for log.
 */
export function resolveRange(
  data: Float32Array,
  options: Pick<RenderOptions, "scale" | "symmetric" | "range">,
): [number, number] {
  const log = options.scale === "log";
  let [low, high] = options.range ?? dataRange(data, options.scale);
  if (log) {
    if (!(low > 0) || !(high > 0)) {
      const [dataLow, dataHigh] = dataRange(data, "log");
      if (!(low > 0)) low = dataLow;
      if (!(high > 0)) high = dataHigh;
    }
    if (!(low > 0) || !(high > 0)) return [1, 10];
    if (low > high) [low, high] = [high, low];
    return low < high ? [low, high] : [low / 10, high * 10];
  }
  if (options.symmetric) {
    const m = Math.max(Math.abs(low), Math.abs(high));
    return m > 0 && Number.isFinite(m) ? [-m, m] : [-1, 1];
  }
  if (!Number.isFinite(low) || !Number.isFinite(high)) return [0, 1];
  if (low > high) [low, high] = [high, low];
  if (low < high) return [low, high];
  const widen = Math.abs(low) || 1;
  return [low - widen, high + widen];
}

/**
 * Colours the array into an ImageData of n_x × n_y pixels (column = x index, row 0 =
 * largest y). Values map to entry floor((v - low) / (high - low) * 256), clamped to
 * 0…255, as matplotlib's Normalize does; log maps log(v) the same way, and v ≤ 0 takes
 * the lowest colour. NaN pixels are transparent (no colour is honest for them); ±Inf
 * clamp to the end colours like any value outside the range.
 *
 * Pass `target` (e.g. from `ctx.createImageData`) to reuse its pixels; it must be
 * n_x × n_y. Cost per node: one packed-RGBA lookup and one 32-bit store, in
 * cache-friendly tiles for the transpose; log adds a table lookup (see paintLog). A
 * 2000 × 2000 array takes ~25 ms linear and ~50 ms log, plus ~15 ms when the range
 * has to be found from the data (pass the header's min/max as `range` to skip it).
 */
export function renderToImageData(
  data: Float32Array,
  shape: Shape,
  options: RenderOptions,
  target?: ImageData,
): ImageData {
  const [nx, ny] = shape;
  if (!(nx > 0 && ny > 0) || data.length !== nx * ny) {
    throw new RangeError(
      `renderToImageData: ${data.length} values do not fill shape [${nx}, ${ny}]`,
    );
  }
  const image = target ?? new ImageData(nx, ny);
  if (image.width !== nx || image.height !== ny) {
    throw new RangeError(
      `renderToImageData: target is ${image.width}×${image.height}, the data ${nx}×${ny}`,
    );
  }
  const pixels = new Uint32Array(image.data.buffer, image.data.byteOffset, nx * ny);
  const lut = packedLut(options.colormap);
  const [low, high] = resolveRange(data, options);
  if (options.scale === "log") {
    const bits = new Uint32Array(data.buffer, data.byteOffset, data.length);
    paintLog(bits, nx, ny, pixels, lut, Math.log2(low), Math.log2(high));
  } else {
    paintLinear(data, nx, ny, pixels, lut, low, high);
  }
  return image;
}

/*
 * The two painters walk the same 64 × 64 tiles: node (i, j) = data[i * ny + j] goes to
 * pixel (column i, row ny - 1 - j). Tiles keep the column reads and the row writes of
 * this transpose in cache. They are two loops rather than one with a branch so each
 * stays small enough for the JIT to keep everything in registers.
 *
 * Both compute t = (u - centre) · 256 / (high - low) + 128, u = v or log2 v: the entry
 * floor((u - low) / (high - low) · 256), except that the range's centre lands on exactly
 * 128, so the 0 of a symmetric range is the colormap's centre for any m.
 *
 * lutSlot(t) is the shifted-LUT slot: 1 + floor(t) clamped to 1…256. NaN fails both
 * comparisons and (NaN + 1) | 0 is 0, so NaN, and only NaN, lands on the transparent
 * slot 0, with no separate test in the loop (a third faster than testing each value).
 */
const TILE = 64;
const POSITIVE_INFINITY_BITS = 0x7f800000;

function lutSlot(t: number): number {
  return t <= 0 ? 1 : t >= TOP ? COLORMAP_SIZE : (t + 1) | 0;
}

function paintLinear(
  data: Float32Array,
  nx: number,
  ny: number,
  pixels: Uint32Array,
  lut: Uint32Array,
  low: number,
  high: number,
): void {
  const centre = (low + high) / 2;
  const perUnit = COLORMAP_SIZE / (high - low);
  for (let i0 = 0; i0 < nx; i0 += TILE) {
    const i1 = Math.min(i0 + TILE, nx);
    for (let j0 = 0; j0 < ny; j0 += TILE) {
      const j1 = Math.min(j0 + TILE, ny);
      for (let i = i0; i < i1; i++) {
        let src = i * ny + j0;
        let dst = (ny - 1 - j0) * nx + i;
        for (let j = j0; j < j1; j++, src++, dst -= nx) {
          // lutSlot(t) written out: measured, the call costs this loop a third.
          const t = ((data[src] as number) - centre) * perUnit + HALF;
          pixels[dst] = lut[t <= 0 ? 1 : t >= TOP ? COLORMAP_SIZE : (t + 1) | 0] as number;
        }
      }
    }
  }
}

/**
 * The slot of log2 colouring for one float32 bit pattern (IEEE 754: sign 1 bit, exponent
 * 8, mantissa 23): v ≤ 0 and -Inf take the lowest colour, +Inf the highest, NaN (of
 * either sign) is transparent.
 */
function logSlot(b: number, centre: number, perUnit: number): number {
  let t: number;
  if (b > 0 && b < POSITIVE_INFINITY_BITS) {
    t = (log2Float32(b) - centre) * perUnit + HALF; // 0 < v < +Inf
  } else if (b === POSITIVE_INFINITY_BITS) {
    t = Infinity;
  } else if ((b & 0x7fffffff) > POSITIVE_INFINITY_BITS) {
    t = NaN; // exponent all ones, mantissa not 0: NaN, whatever its sign
  } else {
    t = -Infinity; // ±0, a negative value or -Inf: no logarithm
  }
  return lutSlot(t);
}

/*
 * Most nodes of a log render skip the logarithm. The bit patterns sharing their top 17
 * bits form a bucket of neighbouring values, 2^-8 ≈ 0.4 % wide. logSlot is monotonic in
 * the pattern over the positive values and the lowest slot for every negative one, so
 * when a bucket's first and last patterns get the same slot, every pattern in between
 * does too and the node reads it from this table. Only buckets that straddle a bin edge
 * (or mix +Inf and NaN) are marked -1 and computed per node. Same pixels as computing
 * every node, about half the time on a large field; the table costs ~2 ms per render.
 */
const BUCKET_SHIFT = 15;
const bucketSlots = new Int16Array(2 ** (32 - BUCKET_SHIFT));

/** As paintLinear on log2 v, read from the float32 bits through bucketSlots. */
function paintLog(
  bits: Uint32Array,
  nx: number,
  ny: number,
  pixels: Uint32Array,
  lut: Uint32Array,
  log2Low: number,
  log2High: number,
): void {
  const centre = (log2Low + log2High) / 2;
  const perUnit = COLORMAP_SIZE / (log2High - log2Low);
  const bucketSize = 2 ** BUCKET_SHIFT;
  for (let key = 0; key < bucketSlots.length; key++) {
    const first = key * bucketSize;
    const slot = logSlot(first, centre, perUnit);
    bucketSlots[key] = slot === logSlot(first + bucketSize - 1, centre, perUnit) ? slot : -1;
  }
  for (let i0 = 0; i0 < nx; i0 += TILE) {
    const i1 = Math.min(i0 + TILE, nx);
    for (let j0 = 0; j0 < ny; j0 += TILE) {
      const j1 = Math.min(j0 + TILE, ny);
      for (let i = i0; i < i1; i++) {
        let src = i * ny + j0;
        let dst = (ny - 1 - j0) * nx + i;
        for (let j = j0; j < j1; j++, src++, dst -= nx) {
          const b = bits[src] as number;
          const slot = bucketSlots[b >>> BUCKET_SHIFT] as number;
          pixels[dst] = lut[slot >= 0 ? slot : logSlot(b, centre, perUnit)] as number;
        }
      }
    }
  }
}

/** The rectangle the image covers, in µm, and the node spacing. */
export interface FieldBounds {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  dx: number;
  dy: number;
}

/**
 * Node spacing from the extent, and the image's outer edges half a cell beyond the
 * first and last nodes. An axis with one node borrows the other axis's spacing (or 1 µm).
 */
export function fieldBounds(shape: Shape, extent: Extent): FieldBounds {
  const [nx, ny] = shape;
  const [x0, x1, y0, y1] = extent;
  const ownDx = nx > 1 ? (x1 - x0) / (nx - 1) : 0;
  const ownDy = ny > 1 ? (y1 - y0) / (ny - 1) : 0;
  const dx = ownDx || ownDy || 1;
  const dy = ownDy || ownDx || 1;
  return { xMin: x0 - dx / 2, xMax: x1 + dx / 2, yMin: y0 - dy / 2, yMax: y1 + dy / 2, dx, dy };
}

/**
 * The node nearest to (xUm, yUm): its value and indices, `data[i * n_y + j]`. Null
 * outside the image (more than half a cell beyond the first or last node).
 */
export function sampleAt(
  data: Float32Array,
  shape: Shape,
  extent: Extent,
  xUm: number,
  yUm: number,
): { value: number; i: number; j: number } | null {
  const [nx, ny] = shape;
  if (!(nx > 0 && ny > 0) || data.length !== nx * ny) return null;
  const { dx, dy } = fieldBounds(shape, extent);
  const u = (xUm - extent[0]) / dx;
  const w = (yUm - extent[2]) / dy;
  if (!(u >= -0.5 && u <= nx - 0.5 && w >= -0.5 && w <= ny - 0.5)) return null;
  const i = Math.min(nx - 1, Math.max(0, Math.round(u)));
  const j = Math.min(ny - 1, Math.max(0, Math.round(w)));
  return { value: data[i * ny + j] as number, i, j };
}

/** µm of node (i, j). */
export function nodePosition(shape: Shape, extent: Extent, i: number, j: number): [number, number] {
  const { dx, dy } = fieldBounds(shape, extent);
  return [extent[0] + i * dx, extent[2] + j * dy];
}

/**
 * A colour-scale tick: 3 significant figures, positional between 1e-3 and 1e4,
 * exponential outside ("1.23e-5"), trailing zeros dropped. Data, so it goes in <Value>.
 */
export function formatTick(value: number): string {
  if (value === 0) return "0"; // also -0
  if (!Number.isFinite(value)) return String(value);
  const magnitude = Math.abs(value);
  if (magnitude >= 1e-3 && magnitude < 1e4) return String(Number(value.toPrecision(3)));
  return value.toExponential(2).replace(/\.?0+e/, "e").replace("e+", "e");
}
