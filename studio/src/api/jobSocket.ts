/**
 * `WS /api/jobs/{job_id}` (plan-u1 §13.3). Text frames are JSON messages told apart by
 * `type`; binary frames are live field snapshots in the §13.1 layout. The token rides
 * as a subprotocol because browsers cannot set headers on a WebSocket.
 */
import { decodeArray } from "../field/binary";
import type { components } from "./schema";

export type JobMessage = components["schemas"]["JobMessage"];
export type SnapshotHeader = components["schemas"]["SnapshotHeader"];
export type JobProgress = components["schemas"]["Progress"];
export type JobLogLine = components["schemas"]["LogLine"];
export type JobDone = components["schemas"]["DoneMessage"];
export type JobStartedMessage = components["schemas"]["StartedMessage"];

export interface JobSocketHandlers {
  onMessage: (message: JobMessage) => void;
  onSnapshot: (header: SnapshotHeader, data: Float32Array) => void;
  /** The socket closed; `clean` is false when it dropped before the job's `done`. */
  onClose: (clean: boolean) => void;
}

export const JOB_PROTOCOL = "etalon.v1";

export function jobSocketUrl(jobId: string, location: Location = window.location): string {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}/api/jobs/${encodeURIComponent(jobId)}`;
}

/** Opens the job's socket; returns a function that closes it. */
export function openJobSocket(
  jobId: string,
  token: string | null,
  handlers: JobSocketHandlers,
  WebSocketImpl: typeof WebSocket = WebSocket,
): () => void {
  const protocols = token ? [JOB_PROTOCOL, `token.${token}`] : [JOB_PROTOCOL];
  const socket = new WebSocketImpl(jobSocketUrl(jobId), protocols);
  socket.binaryType = "arraybuffer";
  let finished = false;
  let closedByUs = false;
  socket.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
    if (typeof event.data === "string") {
      const message = JSON.parse(event.data) as JobMessage;
      if (message.type === "done") finished = true;
      handlers.onMessage(message);
    } else {
      const { header, data } = decodeArray<SnapshotHeader>(event.data);
      handlers.onSnapshot(header, data);
    }
  };
  socket.onclose = () => {
    if (!closedByUs) handlers.onClose(finished);
  };
  return () => {
    closedByUs = true;
    socket.close();
  };
}
