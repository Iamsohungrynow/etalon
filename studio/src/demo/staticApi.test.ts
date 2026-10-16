// The demo's static adapter and run replay, against a small hand-made recording.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { openReplay } from "./replaySocket";
import { createDemoFetch, requestKey, resetManifest, type DemoManifest } from "./staticApi";

const BASE = "/demo-data/";
const ID = "abc123def456";
const RESULT = `${ID}~20261016T145335Z`;

function header(n: number): ArrayBuffer {
  // §13.1: [uint32 N][JSON][pad to 4][float32]
  const text = new TextEncoder().encode(
    JSON.stringify({ kind: "snapshot", shape: [1, n], extent: [0, 1, 0, 1], min: 0, max: 1, component: "Hz", step: 7, unit: "1" }),
  );
  const start = Math.ceil((4 + text.length) / 4) * 4;
  const buffer = new ArrayBuffer(start + 4 * n);
  new DataView(buffer).setUint32(0, text.length, true);
  new Uint8Array(buffer, 4, text.length).set(text);
  new Float32Array(buffer, start, n).set(Array.from({ length: n }, (_, i) => i));
  return buffer;
}

const SNAPSHOT = header(3);
const MANIFEST: DemoManifest = {
  version: 1,
  recorded_at: "2026-10-16T14:53:57+00:00",
  workspace: "~/etalon-demo",
  responses: {
    "GET /api/workspace": { file: "r/ws.json", status: 200, type: "application/json" },
    "GET /api/settings": { file: "r/settings.json", status: 200, type: "application/json" },
    [`GET /api/results/${RESULT}/fields/line?component=Hz&quantity=abs&wavelength_index=1`]: {
      file: "r/field.bin",
      status: 200,
      type: "application/octet-stream",
    },
    "GET /api/simulations/broken/spec": { file: "r/broken.json", status: 422, type: "application/json" },
  },
  jobs: { [ID]: { result_id: RESULT, frames: "r/frames.json", snapshots: "r/snaps.bin" } },
};
const FILES: Record<string, BodyInit> = {
  "manifest.json": JSON.stringify(MANIFEST),
  "r/ws.json": JSON.stringify({ folder: "~/etalon-demo", simulations: [{ id: ID, status: "done", job_id: null }] }),
  "r/settings.json": JSON.stringify({ language: "system", theme: "dark", workspace: "~/etalon-demo" }),
  "r/field.bin": SNAPSHOT,
  "r/broken.json": JSON.stringify({ code: "script_failed" }),
  "r/frames.json": JSON.stringify({
    frames: [
      { t: 1, message: { type: "started", total: 10 } },
      { t: 2, snapshot: [0, SNAPSHOT.byteLength] },
      { t: 3, message: { type: "progress", step: 10, total: 10 } },
      { t: 4, message: { type: "done", status: "done", result_id: RESULT } },
    ],
  }),
  "r/snaps.bin": SNAPSHOT,
};

let now = 0;
beforeEach(() => {
  now = 0;
  vi.spyOn(performance, "now").mockImplementation(() => now);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      const name = path.startsWith(BASE) ? path.slice(BASE.length) : path;
      const body = FILES[name];
      return body === undefined ? new Response("missing", { status: 404 }) : new Response(body);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
  resetManifest();
});

const call = (path: string, init?: RequestInit) =>
  createDemoFetch(BASE)(new Request(`http://127.0.0.1:8792${path}`, init));

describe("the demo's static API", () => {
  it("keys requests by decoded path and sorted query", () => {
    const url = new URL(`http://x/api/results/${encodeURIComponent(RESULT)}/fields/line?wavelength_index=1&quantity=abs&component=Hz`);
    expect(requestKey("GET", url)).toBe(
      `GET /api/results/${RESULT}/fields/line?component=Hz&quantity=abs&wavelength_index=1`,
    );
  });

  it("answers a recorded GET with its body and status", async () => {
    const field = await call(`/api/results/${RESULT}/fields/line?component=Hz&quantity=abs&wavelength_index=1`);
    expect(field.status).toBe(200);
    expect((await field.arrayBuffer()).byteLength).toBe(SNAPSHOT.byteLength);
    const broken = await call("/api/simulations/broken/spec");
    expect(broken.status).toBe(422);
    expect(await broken.json()).toEqual({ code: "script_failed" });
    expect((await call("/api/simulations/nope/spec")).status).toBe(404);
  });

  it("keeps settings changes in memory but not a new workspace", async () => {
    const api = createDemoFetch(BASE);
    const put = (body: object) =>
      api(new Request("http://x/api/settings", { method: "PUT", body: JSON.stringify(body) }));
    expect((await put({ language: "zh-CN", workspace: "C:/elsewhere" })).status).toBe(422);
    expect((await put({ language: "zh-CN", workspace: "~/etalon-demo" })).status).toBe(200);
    const settings = await api(new Request("http://x/api/settings"));
    expect(await settings.json()).toMatchObject({ language: "zh-CN" });
  });

  it("starts a replay: the row runs until the recording ends, then is done again", async () => {
    const api = createDemoFetch(BASE);
    const run = await api(new Request(`http://x/api/simulations/${ID}/run`, { method: "POST" }));
    expect(run.status).toBe(202);
    const started = (await run.json()) as { job_id: string; result_id: string };
    expect(started).toEqual({ job_id: `demo.1.${ID}`, result_id: RESULT });
    const again = await api(new Request(`http://x/api/simulations/${ID}/run`, { method: "POST" }));
    expect(again.status).toBe(409);
    const row = async () =>
      ((await (await api(new Request("http://x/api/workspace"))).json()) as { simulations: { status: string; job_id: string | null }[] }).simulations[0];
    expect(await row()).toMatchObject({ status: "running", job_id: started.job_id });
    now = 4001;
    expect(await row()).toMatchObject({ status: "done", job_id: null });
  });

  it("answers what needs the local Studio with 503 demo_static", async () => {
    const create = await call("/api/simulations", { method: "POST", body: "{}" });
    expect(create.status).toBe(503);
    expect(await create.json()).toMatchObject({ code: "demo_static" });
    expect((await call("/api/jobs/demo.1.x", { method: "DELETE" })).status).toBe(503);
  });
});

describe("the demo's run replay", () => {
  it("plays the recorded frames at their times, then closes cleanly", async () => {
    vi.useFakeTimers();
    const onMessage = vi.fn();
    const onSnapshot = vi.fn();
    const onClose = vi.fn();
    openReplay(`demo.1.${ID}`, { onMessage, onSnapshot, onClose }, BASE);
    await vi.advanceTimersByTimeAsync(1500);
    expect(onMessage.mock.calls.map(([m]) => m.type)).toEqual(["started"]);
    await vi.advanceTimersByTimeAsync(1000);
    expect(onSnapshot).toHaveBeenCalledTimes(1);
    expect(Array.from(onSnapshot.mock.calls[0]?.[1] as Float32Array)).toEqual([0, 1, 2]);
    await vi.advanceTimersByTimeAsync(2000);
    expect(onMessage.mock.calls.map(([m]) => m.type)).toEqual(["started", "progress", "done"]);
    expect(onClose).toHaveBeenCalledWith(true);
  });

  it("stops when closed, and reports a missing recording as a lost connection", async () => {
    vi.useFakeTimers();
    const onMessage = vi.fn();
    const stop = openReplay(`demo.1.${ID}`, { onMessage, onSnapshot: vi.fn(), onClose: vi.fn() }, BASE);
    await vi.advanceTimersByTimeAsync(1500);
    stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(onMessage).toHaveBeenCalledTimes(1);

    const onClose = vi.fn();
    openReplay("demo.1.unknown", { onMessage: vi.fn(), onSnapshot: vi.fn(), onClose }, BASE);
    await vi.advanceTimersByTimeAsync(10);
    expect(onClose).toHaveBeenCalledWith(false);
  });
});
