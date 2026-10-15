// V7: the Workspace screen's states, rows, links, filter and banners.
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { SimulationRow } from "../../api/client";
import { FOLDER, NO_GPU, fakeServer, json, makeRow } from "../../test/fakeServer";
import { renderApp } from "../../test/renderApp";
import { rowTarget } from "./rowTarget";

const now = new Date();
const minutesAgo = (m: number) => new Date(now.getTime() - m * 60_000).toISOString();

const ROWS: SimulationRow[] = [
  makeRow({ path: "bend_euler.py", status: "cancelled", last_run: minutesAgo(3 * 24 * 60), backend: "cpu", wall_time_s: 3840 }),
  makeRow({ path: "dc_gap200.py", status: "failed", backend: "cuda:0" }),
  makeRow({ path: "mmi_1x2.py" }),
  makeRow({ path: "rings/ring_r10_g200.py", status: "done", last_run: minutesAgo(1), backend: "cuda:0", cells: 42_300_000, wall_time_s: 192, stale: true }),
  makeRow({ path: "rings/ring_r10_g180.py", status: "running", step: 11_000, total_steps: 26_400, eta_s: 130, backend: "cuda:0", cells: 42_300_000 }),
  makeRow({ path: "broken.py", status: "unknown", status_reason: "invalid_json" }),
];

function serverWith(simulations: SimulationRow[], extra = {}) {
  return fakeServer({ workspace: { folder: FOLDER, simulations, truncated: false }, ...extra });
}

describe("V7: Workspace", () => {
  it("shows a loading state with text first", async () => {
    let release: (r: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => (release = resolve));
    renderApp("/", fakeServer({}, { "GET /api/workspace": () => pending }));
    expect(await screen.findByText("Scanning workspace…")).toBeVisible();
    release(json({ folder: FOLDER, simulations: [], truncated: false }));
    expect(await screen.findByText("No simulation scripts here yet")).toBeVisible();
  });

  it("explains an empty folder and links to Settings", async () => {
    renderApp("/", serverWith([]));
    expect(await screen.findByRole("heading", { name: "No simulation scripts here yet" })).toBeVisible();
    expect(screen.getByText(".py")).toHaveAttribute("translate", "no");
    expect(screen.getByRole("link", { name: "Choose another folder" })).toHaveAttribute("href", "/settings");
  });

  it("lists every row with status words, numbers and links by status", async () => {
    renderApp("/", serverWith(ROWS));
    const table = await screen.findByRole("table", { name: "Simulations in this workspace" });
    expect(screen.getByTestId("workspace-count")).toHaveTextContent("6 simulations");
    const row = (name: string) => screen.getByRole("link", { name }).closest("[role=row]") as HTMLElement;
    const done = row("rings/ring_r10_g200.py");
    expect(within(done).getByText("done")).toBeInTheDocument();
    expect(within(done).getByText("stale")).toBeInTheDocument();
    expect(within(done).getByText("42.3 M")).toBeInTheDocument();
    expect(within(done).getByText("3m12")).toBeInTheDocument();
    expect(within(done).getByText(/today$/)).toBeInTheDocument();
    const running = row("rings/ring_r10_g180.py");
    expect(within(running).getByText("11 k / 26.4 k")).toBeInTheDocument();
    expect(within(running).getByText("~2m")).toBeInTheDocument();
    expect(within(row("bend_euler.py")).getByText("1h04m")).toBeInTheDocument();
    expect(within(row("broken.py")).getByText("unknown").parentElement).toHaveAttribute(
      "title",
      "The run status file is not valid JSON.",
    );
    expect(within(table).getAllByRole("link")).toHaveLength(6);
    for (const r of ROWS) {
      expect(screen.getByRole("link", { name: r.path })).toHaveAttribute("href", rowTarget(r));
    }
  });

  it("routes each status to its screen", () => {
    const id = "abc";
    expect(rowTarget({ id, status: "draft" })).toBe("/sim/abc/setup");
    expect(rowTarget({ id, status: "unknown" })).toBe("/sim/abc/setup");
    expect(rowTarget({ id, status: "running" })).toBe("/sim/abc/run");
    for (const status of ["done", "failed", "cancelled"] as const) {
      expect(rowTarget({ id, status })).toBe("/sim/abc/results");
    }
  });

  it("filters by name or folder, and says when nothing matches", async () => {
    renderApp("/", serverWith(ROWS));
    const filter = await screen.findByRole("textbox", { name: "Filter by name or folder" });
    await userEvent.type(filter, "rings/");
    expect(screen.getAllByRole("link", { name: /^rings\// })).toHaveLength(2);
    expect(screen.getByTestId("workspace-count")).toHaveTextContent("2 of 6");
    await userEvent.clear(filter);
    await userEvent.type(filter, "nothing-like-this");
    expect(screen.getByText("No scripts match “nothing-like-this”.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Clear filter" }));
    expect(screen.getAllByRole("link", { name: /\.py$/ })).toHaveLength(6);
  });

  it("shows the no-GPU banner without blocking the list", async () => {
    renderApp("/", serverWith(ROWS, { system: NO_GPU }));
    expect(await screen.findByText("No CUDA device found; runs use the CPU backend.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Backend settings" })).toHaveAttribute("href", "/settings");
    expect(screen.getAllByRole("link", { name: /\.py$/ })).toHaveLength(6);
  });

  it("warns when the scan was truncated", async () => {
    renderApp("/", fakeServer({ workspace: { folder: FOLDER, simulations: ROWS, truncated: true } }));
    expect(await screen.findByText(/only the first 5000 are listed/)).toBeVisible();
  });

  it("explains a missing folder, with Retry and a way to Settings", async () => {
    const server = fakeServer({}, {
      "GET /api/workspace": () => json({ code: "workspace_missing", message: "gone" }, 404),
    });
    renderApp("/", server);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The workspace folder no longer exists.");
    expect(within(alert).getByText(FOLDER)).toHaveAttribute("translate", "no");
    expect(within(alert).getByRole("link", { name: "Open Settings" })).toHaveAttribute("href", "/settings");
    server.state.workspace = { folder: FOLDER, simulations: ROWS, truncated: false };
    await userEvent.click(within(alert).getByRole("button", { name: "Retry" }));
  });

  it("shows other failures with their status and retries", async () => {
    let fail = true;
    const server = fakeServer({}, {
      "GET /api/workspace": () =>
        fail ? json({ code: "oops", message: "boom" }, 500) : json({ folder: FOLDER, simulations: ROWS, truncated: false }),
    });
    renderApp("/", server);
    expect(await screen.findByText("The Studio server answered with an error (500).")).toBeVisible();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("table")).toBeVisible();
  });

  it("speaks Chinese, keeping file names and numbers as data", async () => {
    const server = serverWith(ROWS);
    server.state.settings.language = "zh-CN"; // "system" would follow jsdom's en-US
    renderApp("/", server, "zh-CN");
    expect(await screen.findByRole("heading", { name: "工作区" })).toBeVisible();
    expect(await screen.findByTestId("workspace-count")).toHaveTextContent("6 个仿真");
    expect(screen.getByRole("columnheader", { name: "上次运行" })).toBeInTheDocument();
    expect(screen.getAllByText("运行中").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "rings/ring_r10_g200.py" })).toHaveAttribute("translate", "no");
  });
});
