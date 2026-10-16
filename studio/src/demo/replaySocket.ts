/**
 * The demo build's job socket: it replays a recorded run's WebSocket frames (started,
 * history, progress, log, live Hz snapshots, done) at the times they arrived when
 * studio/scripts/record_demo.py recorded the run, so progress, energy and the live field
 * are the solver's own.
 */
import type { JobSocketHandlers, SnapshotHeader } from "../api/jobSocket";
import { decodeArray } from "../field/binary";
import { DEMO_DATA_BASE } from "./mode";
import { loadFrames, loadManifest, simulationOfDemoJob } from "./staticApi";

async function loadRun(jobId: string, base: string) {
  const simulationId = simulationOfDemoJob(jobId);
  const manifest = await loadManifest(base);
  const job = simulationId ? manifest.jobs[simulationId] : undefined;
  if (!job) throw new Error(`no recorded run for job ${jobId}`);
  const [frames, snapshots] = await Promise.all([
    loadFrames(job, base),
    fetch(`${base}${job.snapshots}`).then((r) => r.arrayBuffer()),
  ]);
  return { frames, snapshots };
}

/** Replays the recorded run behind `jobId`; returns a function that stops it. */
export function openReplay(
  jobId: string,
  handlers: JobSocketHandlers,
  base = DEMO_DATA_BASE,
): () => void {
  const opened = performance.now();
  const timers: ReturnType<typeof setTimeout>[] = [];
  let stopped = false;

  loadRun(jobId, base).then(
    ({ frames, snapshots }) => {
      if (stopped) return;
      const loaded = performance.now() - opened;
      for (const frame of frames) {
        const play = () => {
          if (stopped) return;
          if ("message" in frame) {
            handlers.onMessage(frame.message);
            if (frame.message.type === "done") handlers.onClose(true);
          } else {
            const [offset, length] = frame.snapshot;
            const { header, data } = decodeArray<SnapshotHeader>(
              snapshots.slice(offset, offset + length),
            );
            handlers.onSnapshot(header, data);
          }
        };
        timers.push(setTimeout(play, Math.max(0, frame.t * 1000 - loaded)));
      }
    },
    () => {
      if (!stopped) handlers.onClose(false);
    },
  );

  return () => {
    stopped = true;
    for (const timer of timers) clearTimeout(timer);
  };
}
