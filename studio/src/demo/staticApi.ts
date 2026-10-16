/**
 * The demo build's stand-in for the Studio server (docs/plan-demo.md). It answers the
 * UI's API requests from the recorded answers in studio/demo-data/, which
 * studio/scripts/record_demo.py captured from the real server and real M0 solver runs,
 * so every number on the page is the solver's. Nothing but those same-origin files is
 * fetched.
 *
 * - A recorded GET is answered with its recorded body and status.
 * - Settings changes (language, theme, units) are kept in memory for this tab; the
 *   workspace folder cannot change.
 * - Run replays the simulation's recorded run (replaySocket.ts).
 * - Everything else needs the local Studio and answers 503 `demo_static`.
 */
import type { JobMessage } from "../api/jobSocket";
import { DEMO_DATA_BASE } from "./mode";

export interface RecordedAnswer {
  file: string;
  status: number;
  type: string;
}

export interface RecordedJob {
  result_id: string;
  /** JSON: `{ frames: [{ t, message } | { t, snapshot: [offset, length] }] }`. */
  frames: string;
  /** The live frames' §13.1 arrays, back to back. */
  snapshots: string;
}

export interface DemoManifest {
  version: number;
  recorded_at: string;
  workspace: string;
  /** Keyed by `request_key()` in record_demo.py: `GET /api/x?a=1&b=2`, query sorted. */
  responses: Record<string, RecordedAnswer>;
  /** Keyed by simulation id. */
  jobs: Record<string, RecordedJob>;
}

export const DEMO_UNAVAILABLE = "demo_static";

export type RecordedFrame =
  | { t: number; message: JobMessage }
  | { t: number; snapshot: [offset: number, length: number] };

let manifestPromise: Promise<DemoManifest> | null = null;
const framePromises = new Map<string, Promise<RecordedFrame[]>>();

export function loadManifest(base = DEMO_DATA_BASE): Promise<DemoManifest> {
  manifestPromise ??= fetch(`${base}manifest.json`).then(async (response) => {
    if (!response.ok) throw new Error(`demo manifest: HTTP ${response.status}`);
    return (await response.json()) as DemoManifest;
  });
  return manifestPromise;
}

/** A recorded run's frames, with the time (s after `POST .../run`) each arrived. */
export function loadFrames(job: RecordedJob, base = DEMO_DATA_BASE): Promise<RecordedFrame[]> {
  let frames = framePromises.get(job.frames);
  if (!frames) {
    frames = fetch(`${base}${job.frames}`).then(async (response) => {
      if (!response.ok) throw new Error(`demo data ${job.frames}: HTTP ${response.status}`);
      return ((await response.json()) as { frames: RecordedFrame[] }).frames;
    });
    framePromises.set(job.frames, frames);
  }
  return frames;
}

/** For tests: forget the loaded manifest and frames. */
export function resetManifest(): void {
  manifestPromise = null;
  framePromises.clear();
}

/** The manifest key of a request: path segments decoded, query parameters sorted by name. */
export function requestKey(method: string, url: URL): string {
  const path = url.pathname.split("/").map(decodeURIComponent).join("/");
  const names = [...new Set(url.searchParams.keys())].sort();
  if (names.length === 0) return `${method} ${path}`;
  const query = names.map((name) => `${name}=${url.searchParams.get(name) ?? ""}`).join("&");
  return `${method} ${path}?${query}`;
}

/** The replay's job id carries the simulation id: `demo.<n>.<simulation id>`. */
export function demoJobId(simulationId: string, n: number): string {
  return `demo.${n}.${simulationId}`;
}

export function simulationOfDemoJob(jobId: string): string | null {
  const match = /^demo\.\d+\.(.+)$/.exec(jobId);
  return match?.[1] ?? null;
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function unavailable(): Response {
  return json(
    {
      code: DEMO_UNAVAILABLE,
      message: "This demo replays recorded results; this action needs the local Studio.",
    },
    503,
  );
}

/** A `fetch` for openapi-fetch that answers from the recording. */
export function createDemoFetch(base = DEMO_DATA_BASE): typeof fetch {
  let settings: Record<string, unknown> | null = null;
  let runs = 0;
  /** Replays under way, by simulation id: the workspace shows them running until `until`. */
  const replaying = new Map<string, { jobId: string; until: number }>();

  function current(simulationId: string) {
    const run = replaying.get(simulationId);
    if (run && performance.now() < run.until) return run;
    replaying.delete(simulationId);
    return null;
  }

  async function workspace(answer: Response): Promise<Response> {
    const body = (await answer.json()) as { simulations: Record<string, unknown>[] };
    for (const row of body.simulations) {
      const run = current(String(row.id));
      if (run) Object.assign(row, { status: "running", job_id: run.jobId, eta_s: null });
    }
    return json(body, answer.status);
  }

  async function recorded(manifest: DemoManifest, key: string): Promise<Response | null> {
    const answer = manifest.responses[key];
    if (!answer) return null;
    const file = await fetch(`${base}${answer.file}`);
    if (!file.ok) throw new Error(`demo data ${answer.file}: HTTP ${file.status}`);
    return new Response(await file.arrayBuffer(), {
      status: answer.status,
      headers: { "content-type": answer.type },
    });
  }

  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    const manifest = await loadManifest(base);
    const key = requestKey(request.method, url);

    if (key === "GET /api/settings") {
      if (!settings) {
        const answer = await recorded(manifest, key);
        // The demo opens in the light (paper) theme; Settings can still switch it.
        if (answer) settings = { ...((await answer.json()) as Record<string, unknown>), theme: "light" };
      }
      if (settings) return json(settings, 200);
    }
    if (key === "PUT /api/settings") {
      const body = (await request.json()) as Record<string, unknown>;
      if (body.workspace !== manifest.workspace) {
        const msg = "the demo's workspace is fixed; the local Studio opens any folder";
        return json({ detail: [{ type: DEMO_UNAVAILABLE, loc: ["body", "workspace"], msg }] }, 422);
      }
      settings = body;
      return json(settings, 200);
    }
    const run = /^POST \/api\/simulations\/([^/]+)\/run$/.exec(key);
    if (run) {
      const simulationId = run[1] ?? "";
      const job = manifest.jobs[simulationId];
      if (!job) return json({ code: "not_found", message: "no recorded run" }, 404);
      const already = current(simulationId);
      if (already) {
        const message = `job ${already.jobId} is running this simulation`;
        return json({ code: "already_running", message, job_id: already.jobId }, 409);
      }
      const frames = await loadFrames(job, base);
      runs += 1;
      const jobId = demoJobId(simulationId, runs);
      const until = performance.now() + (frames.at(-1)?.t ?? 0) * 1000;
      replaying.set(simulationId, { jobId, until });
      return json({ job_id: jobId, result_id: job.result_id }, 202);
    }
    if (request.method !== "GET") return unavailable();
    const answer = await recorded(manifest, key);
    if (!answer) return json({ code: "not_found", message: `not in the recording: ${key}` }, 404);
    return key === "GET /api/workspace" ? workspace(answer) : answer;
  };
}
