// Run: idle, live progress over the (fake) WebSocket, cancel, the outcome panels.
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "../../test/FakeWebSocket";
import { FOLDER, fakeServer, json, makeRow } from "../../test/fakeServer";
import { renderApp } from "../../test/renderApp";

vi.mock("../../components/FieldCanvas", async () => ({ FieldCanvas: (await import("../../test/heavyStubs")).FieldCanvasStub }));
vi.mock("../../components/Chart", async () => ({ Chart: (await import("../../test/heavyStubs")).ChartStub }));

const ID = "abc123def456";

beforeEach(() => vi.stubGlobal("WebSocket", FakeWebSocket));
afterEach(() => {
  vi.unstubAllGlobals();
  FakeWebSocket.instances = [];
});

function server(row = makeRow({ id: ID, path: "strip.py" })) {
  return fakeServer(
    { workspace: { folder: FOLDER, simulations: [row], truncated: false } },
    {
      "POST /api/simulations/abc123def456/run": () => json({ job_id: "job-1", result_id: `${ID}~1` }, 202),
      "DELETE /api/jobs/job-1": () => json({ status: "cancelling" }, 202),
      "GET /api/simulations/abc123def456/spec": () => json({ code: "x" }, 500),
    },
  );
}

const progress = (step: number, elapsed: number) => ({
  type: "progress",
  step,
  total: 2000,
  elapsed_s: elapsed,
  eta_s: 30,
  cells_per_s: 2.5e8,
  energy: step,
});

describe("Run", () => {
  it("is idle until started, then follows the job live", async () => {
    renderApp(`/sim/${ID}/run`, server());
    expect(await screen.findByRole("heading", { name: "This simulation is not running" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const socket = FakeWebSocket.last;
    expect(socket.url).toContain("/api/jobs/job-1");
    expect(screen.getByText("Connecting to the run…")).toBeVisible();

    act(() => {
      socket.receive({ type: "started", total: 2000, grid: [200, 100], dt_s: 1e-17, backend: "cuda:0", device: "NVIDIA GeForce RTX 4060 Ti", snapshots: true });
      socket.receive({ type: "history", progress: [], log: [{ type: "log", stream: "etalon", line: "grid 200 x 100" }] });
    });
    expect(screen.getByText("Preparing the solver…")).toBeVisible();
    act(() => socket.receive(progress(500, 5)));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");
    expect(screen.getByText("500 / 2 k")).toBeVisible();
    expect(screen.getByText("cuda:0 · NVIDIA GeForce RTX 4060 Ti")).toBeVisible();
    expect(screen.getByText("grid 200 x 100")).toBeVisible();
    expect(screen.getByText("Waiting for the first frame…")).toBeVisible();
  });

  it("cancels at once early on, and asks first after a minute", async () => {
    const s = server();
    renderApp(`/sim/${ID}/run`, s);
    await userEvent.click(await screen.findByRole("button", { name: "Run" }));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    act(() => FakeWebSocket.last.receive(progress(100, 90)));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByText(/It has been running for 1m30/)).toBeVisible();
    expect(s.calls.some((c) => c.method === "DELETE")).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Cancel the run" }));
    await waitFor(() => expect(s.calls.some((c) => c.method === "DELETE" && c.path === "/api/jobs/job-1")).toBe(true));
    act(() => FakeWebSocket.last.receive({ type: "done", status: "cancelled", result_id: `${ID}~1`, error: null, suggestion: null }));
    expect(screen.getByText(/The run was cancelled/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Open results" })).toHaveAttribute("href", `/sim/${ID}/results`);
  });

  it("shows a failure with its suggestion and traceback", async () => {
    renderApp(`/sim/${ID}/run`, server(makeRow({ id: ID, path: "strip.py", status: "running", job_id: "job-1" })));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    act(() =>
      FakeWebSocket.last.receive({
        type: "done",
        status: "failed",
        result_id: null,
        error: { message: "FloatingPointError: NaN in Hz", traceback: "Traceback (most recent call last):\n  ...", line: null },
        suggestion: "nan",
      }),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The run failed.");
    expect(alert).toHaveTextContent("lower the Courant factor");
    expect(alert).toHaveTextContent("FloatingPointError: NaN in Hz");
  });

  it("offers to reconnect when the socket drops", async () => {
    renderApp(`/sim/${ID}/run`, server(makeRow({ id: ID, path: "strip.py", status: "running", job_id: "job-1" })));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    act(() => FakeWebSocket.last.drop());
    expect(await screen.findByText(/Lost the connection to the run/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Reconnect" }));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2));
  });

  it("keeps the outcome on screen after the row's job_id clears", async () => {
    const s = server(makeRow({ id: ID, path: "strip.py", status: "running", job_id: "job-1" }));
    renderApp(`/sim/${ID}/run`, s);
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    // The real server: once the job ends, the workspace row has no job_id any more.
    s.state.workspace = {
      folder: FOLDER,
      simulations: [makeRow({ id: ID, path: "strip.py", status: "done", last_result_id: `${ID}~1` })],
      truncated: false,
    };
    act(() => FakeWebSocket.last.receive({ type: "done", status: "done", result_id: `${ID}~1`, error: null, suggestion: null }));
    expect(await screen.findByText("The run finished.")).toBeVisible();
    await waitFor(() => expect(s.calls.filter((c) => c.path === "/api/workspace").length).toBeGreaterThan(1));
    expect(screen.getByText("The run finished.")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "This simulation is not running" })).toBeNull();
  });
});
