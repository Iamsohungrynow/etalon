/** Builds a plan-u1 §13.1 binary array for tests: uint32 N, JSON header, padding, float32. */
export function binaryFrame(header: Record<string, unknown>, values: readonly number[]): ArrayBuffer {
  const json = new TextEncoder().encode(JSON.stringify(header));
  const offset = Math.ceil((4 + json.length) / 4) * 4;
  const buffer = new ArrayBuffer(offset + values.length * 4);
  new DataView(buffer).setUint32(0, json.length, true);
  new Uint8Array(buffer, 4, json.length).set(json);
  new Float32Array(buffer, offset, values.length).set(values);
  return buffer;
}
