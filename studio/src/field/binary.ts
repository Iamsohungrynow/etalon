/**
 * Binary float32 arrays from the server (docs/plan-u1.md §13.1): the permittivity
 * slice, monitor fields and live snapshots. Field data never travels as JSON.
 *
 *     [uint32 LE N][N bytes UTF-8 JSON header][zero pad to a multiple of 4][float32 LE data]
 *
 * The data starts at 4 + N rounded up to a multiple of 4, so it is viewed in place as
 * a Float32Array: no copy, however large the array. `shape: [n_x, n_y]` is C order
 * (axis 0 = x, axis 1 = y, y varying fastest), so `data[i * n_y + j]` is node (x_i, y_j).
 */
import { NetworkError, ServerError, SessionEndedError } from "../api/client";
import type { components } from "../api/schema";

/** Any of the three generated headers (permittivity, field, snapshot), told apart by `kind`. */
export type ArrayHeader = components["schemas"]["ArrayHeader"];
export type FieldHeader = components["schemas"]["FieldHeader"];
export type SnapshotHeader = components["schemas"]["SnapshotHeader"];
export type PermittivityHeader = components["schemas"]["PermittivityHeader"];

/** The least a header must carry for the data to be checked against it. */
export interface ShapedHeader {
  readonly shape: readonly [number, number];
}

export interface DecodedArray<H> {
  header: H;
  /** A view into the received buffer (not a copy), `shape[0] * shape[1]` long. */
  data: Float32Array;
}

/** The bytes are not a §13.1 array frame. The message says what is wrong and where. */
export class BinaryFormatError extends Error {
  constructor(message: string) {
    super(`Binary array frame: ${message}`);
    this.name = "BinaryFormatError";
  }
}

const LENGTH_BYTES = 4;
const FLOAT32_BYTES = 4;

/** Float32Array uses the host's byte order; the frames are little-endian. */
const HOST_IS_LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function checkHeader(header: unknown): asserts header is ShapedHeader & Record<string, unknown> {
  if (typeof header !== "object" || header === null || Array.isArray(header)) {
    throw new BinaryFormatError("the header is not a JSON object");
  }
  const { shape, extent } = header as { shape?: unknown; extent?: unknown };
  if (!Array.isArray(shape) || shape.length !== 2 || !shape.every(isNonNegativeInteger)) {
    throw new BinaryFormatError(
      `header.shape must be [n_x, n_y] of non-negative integers, got ${JSON.stringify(shape)}`,
    );
  }
  if (
    extent !== undefined &&
    !(
      Array.isArray(extent) &&
      extent.length === 4 &&
      extent.every((v) => typeof v === "number" && Number.isFinite(v))
    )
  ) {
    throw new BinaryFormatError(
      `header.extent must be [x_first, x_last, y_first, y_last] in µm, got ${JSON.stringify(extent)}`,
    );
  }
}

/**
 * Splits one frame into its JSON header and a Float32Array view of the data.
 * Throws BinaryFormatError if the frame is truncated, the header is not valid UTF-8
 * JSON with a `shape`, the data is not float32-aligned, or the data length is not
 * `shape[0] * shape[1]`.
 */
export function decodeArray<H extends ShapedHeader = ArrayHeader>(
  buffer: ArrayBuffer,
): DecodedArray<H> {
  if (!HOST_IS_LITTLE_ENDIAN) {
    throw new BinaryFormatError("this host is big-endian; Studio needs a little-endian browser");
  }
  if (buffer.byteLength < LENGTH_BYTES) {
    throw new BinaryFormatError(
      `${buffer.byteLength} bytes is too short for the 4-byte header length`,
    );
  }
  const headerBytes = new DataView(buffer).getUint32(0, true);
  if (LENGTH_BYTES + headerBytes > buffer.byteLength) {
    throw new BinaryFormatError(
      `the header length (${headerBytes} bytes) runs past the end of the ${buffer.byteLength}-byte frame`,
    );
  }

  let header: unknown;
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(
      new Uint8Array(buffer, LENGTH_BYTES, headerBytes),
    );
    header = JSON.parse(text);
  } catch (cause) {
    throw new BinaryFormatError(`the header is not UTF-8 JSON (${String(cause)})`);
  }
  checkHeader(header);

  const dataStart = Math.ceil((LENGTH_BYTES + headerBytes) / FLOAT32_BYTES) * FLOAT32_BYTES;
  if (dataStart > buffer.byteLength) {
    throw new BinaryFormatError(
      `the padding after the header ends at byte ${dataStart}, past the ${buffer.byteLength}-byte frame`,
    );
  }
  const dataBytes = buffer.byteLength - dataStart;
  if (dataBytes % FLOAT32_BYTES !== 0) {
    throw new BinaryFormatError(
      `the data section is ${dataBytes} bytes, not a whole number of float32 values`,
    );
  }
  const [nx, ny] = header.shape;
  const expected = nx * ny;
  const count = dataBytes / FLOAT32_BYTES;
  if (count !== expected) {
    throw new BinaryFormatError(
      `the data holds ${count} float32 values but header.shape [${nx}, ${ny}] needs ${expected}`,
    );
  }
  return { header: header as unknown as H, data: new Float32Array(buffer, dataStart, count) };
}

async function errorBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * GET an array frame and decode it. The caller supplies headers (the session token)
 * and an AbortSignal through `init`. Errors are the API client's own: NetworkError
 * (server unreachable), SessionEndedError (401), ServerError (any other non-2xx, with
 * the JSON body when there is one), and BinaryFormatError for a malformed frame.
 */
export async function fetchArray<H extends ShapedHeader = ArrayHeader>(
  url: string,
  init?: RequestInit,
): Promise<DecodedArray<H>> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new NetworkError(cause);
  }
  if (response.status === 401) throw new SessionEndedError();
  if (!response.ok) throw new ServerError(response.status, await errorBody(response));
  return decodeArray<H>(await response.arrayBuffer());
}
