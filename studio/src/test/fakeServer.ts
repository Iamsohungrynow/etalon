/** An in-memory stand-in for etalon/studio/server.py, for component and screen tests. */
import { TOKEN_HEADER, type Settings, type SimulationRow, type SystemInfo, type Workspace } from "../api/client";

export type Handler = (request: Request) => Response | Promise<Response>;

export interface Call {
  method: string;
  path: string;
  body: unknown;
  token: string | null;
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const FOLDER = "C:\\Users\\me\\designs";

export function makeRow(overrides: Partial<SimulationRow> & Pick<SimulationRow, "path">): SimulationRow {
  const name = overrides.path.split("/").pop() ?? overrides.path;
  // The server's fallback title for a script without a docstring: "strip.py" → "Strip".
  const words = name.replace(/\.py$/, "").replaceAll("_", " ");
  return {
    id: overrides.id ?? name.replace(/\W/g, "").slice(0, 12).padEnd(12, "0"),
    name,
    title: words.slice(0, 1).toUpperCase() + words.slice(1),
    status: "draft",
    status_reason: null,
    last_run: null,
    backend: null,
    device: null,
    cells: null,
    wall_time_s: null,
    step: null,
    total_steps: null,
    eta_s: null,
    stale: false,
    modified: "2026-10-16T06:00:00Z",
    job_id: null,
    last_result_id: null,
    ...overrides,
  };
}

export const ONE_GPU: SystemInfo = {
  etalon_version: "0.0.1",
  python_version: "3.12.10",
  platform: "Windows 11 (AMD64)",
  cupy_status: "ok",
  cupy_detail: null,
  devices: [
    { index: 0, name: "NVIDIA GeForce RTX 4060 Ti", memory_bytes: 8585216000, compute_capability: "8.9" },
  ],
};

export const NO_GPU: SystemInfo = { ...ONE_GPU, cupy_status: "missing", devices: [] };

export interface FakeServerState {
  settings: Settings;
  workspace: Workspace;
  system: SystemInfo;
}

export function fakeServer(
  initial: Partial<FakeServerState> = {},
  overrides: Record<string, Handler> = {},
) {
  const state: FakeServerState = {
    settings: {
      backend: "auto",
      language: "system",
      theme: "dark",
      units: "um",
      live_snapshots: false,
      workspace: FOLDER,
    },
    workspace: { folder: FOLDER, simulations: [], truncated: false },
    system: ONE_GPU,
    ...initial,
  };
  const calls: Call[] = [];
  const handlers: Record<string, Handler> = {
    "GET /api/workspace": () => json(state.workspace),
    "GET /api/settings": () => json(state.settings),
    "PUT /api/settings": async (request) => {
      state.settings = (await request.json()) as Settings;
      return json(state.settings);
    },
    "GET /api/system": () => json(state.system),
    "GET /api/templates": () =>
      json(
        ["vacuum_pulse", "strip_waveguide", "sharp_bend", "phc_waveguide"].map((id) => ({
          id,
          file: `${id}.py`,
        })),
      ),
    ...overrides,
  };
  const fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const path = new URL(request.url).pathname;
    const body = request.method === "GET" ? undefined : await request.clone().json().catch(() => undefined);
    calls.push({ method: request.method, path, body, token: request.headers.get(TOKEN_HEADER) });
    const handler = handlers[`${request.method} ${path}`];
    return handler ? handler(request) : json({ code: "not_found", message: path }, 404);
  };
  return { fetch: fetch as typeof globalThis.fetch, calls, state };
}

export type FakeServer = ReturnType<typeof fakeServer>;
