// The job socket and its reducer: replay, live messages, snapshots, a dropped connection.
import { afterEach, describe, expect, it, vi } from "vitest";
import { JOB_PROTOCOL, jobSocketUrl, openJobSocket } from "../../api/jobSocket";
import { binaryFrame } from "../../test/binaryFrame";
import { FakeWebSocket } from "../../test/FakeWebSocket";
import { initialJobState, jobReducer, type JobState } from "./useJob";

const progress = (step: number, energy: number) => ({
  type: "progress" as const,
  step,
  total: 1000,
  elapsed_s: step / 100,
  eta_s: (1000 - step) / 100,
  cells_per_s: 2e8,
  energy,
});

afterEach(() => {
  FakeWebSocket.instances = [];
});

describe("job socket", () => {
  it("connects to the job with the token as a subprotocol and decodes both frame kinds", () => {
    const onMessage = vi.fn();
    const onSnapshot = vi.fn();
    const onClose = vi.fn();
    const close = openJobSocket("job 1", "secret", { onMessage, onSnapshot, onClose }, FakeWebSocket as unknown as typeof WebSocket);
    const socket = FakeWebSocket.last;
    expect(socket.url).toBe(jobSocketUrl("job 1"));
    expect(socket.url.endsWith("/api/jobs/job%201")).toBe(true);
    expect(socket.protocols).toEqual([JOB_PROTOCOL, "token.secret"]);
    expect(socket.binaryType).toBe("arraybuffer");

    socket.receive(progress(10, 1));
    expect(onMessage).toHaveBeenCalledWith(progress(10, 1));
    const header = { kind: "snapshot", shape: [2, 2], extent: [0, 1, 0, 1], min: -1, max: 1, component: "Hz", unit: "A/m", step: 10 };
    socket.receive(binaryFrame(header, [1, -1, 0.5, 0]));
    const [decodedHeader, data] = onSnapshot.mock.calls[0] as [typeof header, Float32Array];
    expect(decodedHeader.step).toBe(10);
    expect(Array.from(data)).toEqual([1, -1, 0.5, 0]);

    socket.drop();
    expect(onClose).toHaveBeenCalledWith(false);
    close();
    expect(socket.closed).toBe(true);
  });

  it("calls a close after `done` clean, and stays quiet when we close it", () => {
    const onClose = vi.fn();
    openJobSocket("j", null, { onMessage: vi.fn(), onSnapshot: vi.fn(), onClose }, FakeWebSocket as unknown as typeof WebSocket);
    const socket = FakeWebSocket.last;
    expect(socket.protocols).toEqual([JOB_PROTOCOL]);
    socket.receive({ type: "done", status: "done", result_id: "r", error: null, suggestion: null });
    socket.drop();
    expect(onClose).toHaveBeenCalledWith(true);

    const quiet = vi.fn();
    const close = openJobSocket("k", null, { onMessage: vi.fn(), onSnapshot: vi.fn(), onClose: quiet }, FakeWebSocket as unknown as typeof WebSocket);
    close();
    FakeWebSocket.last.drop();
    expect(quiet).not.toHaveBeenCalled();
  });
});

describe("job reducer", () => {
  const run = (...messages: Parameters<typeof jobReducer>[1][]): JobState =>
    messages.reduce(jobReducer, initialJobState);

  it("replays history, then appends live progress and log lines", () => {
    const state = run(
      { type: "message", message: { type: "started", total: 1000, grid: [100, 80], dt_s: 1e-17, backend: "numpy", device: "cpu", snapshots: false } },
      { type: "message", message: { type: "history", progress: [progress(1, 0.1), progress(2, 0.5)], log: [{ type: "log", stream: "etalon", line: "grid 100 x 80" }] } },
      { type: "message", message: progress(3, 1) },
      { type: "message", message: { type: "log", stream: "stdout", line: "hello" } },
    );
    expect(state.connection).toBe("open");
    expect(state.started?.total).toBe(1000);
    expect(state.progress.map((p) => p.step)).toEqual([1, 2, 3]);
    expect(state.log.map((l) => l.line)).toEqual(["grid 100 x 80", "hello"]);
  });

  it("keeps at most 2000 log lines", () => {
    const lines = Array.from({ length: 2100 }, (_, i) => ({ type: "log" as const, stream: "stdout" as const, line: `l${i}` }));
    const state = run({ type: "message", message: { type: "history", progress: [], log: lines } });
    expect(state.log).toHaveLength(2000);
    expect(state.log[0]?.line).toBe("l100");
  });

  it("marks a dropped connection lost, unless the job is done", () => {
    expect(run({ type: "closed", clean: false }).connection).toBe("lost");
    const done = run(
      { type: "message", message: { type: "done", status: "failed", result_id: null, error: { message: "boom", traceback: "", line: null }, suggestion: "nan" } },
      { type: "closed", clean: false },
    );
    expect(done.connection).not.toBe("lost");
    expect(done.done?.suggestion).toBe("nan");
  });

  it("keeps the latest snapshot", () => {
    const header = {
      kind: "snapshot" as const,
      shape: [1, 1] as [number, number],
      extent: [0, 0, 0, 0] as [number, number, number, number],
      min: 0,
      max: 0,
      component: "Hz",
      unit: "",
      step: 5,
    };
    const state = run({ type: "snapshot", header, data: new Float32Array([2]) });
    expect(state.snapshot?.header.step).toBe(5);
  });
});
