import { useEffect, useReducer } from "react";
import { useApiToken } from "../../api/ApiProvider";
import {
  openJobSocket,
  type JobDone,
  type JobLogLine,
  type JobMessage,
  type JobProgress,
  type JobStartedMessage,
  type SnapshotHeader,
} from "../../api/jobSocket";

const MAX_LOG = 2000;

export interface JobState {
  connection: "connecting" | "open" | "lost";
  started: JobStartedMessage | null;
  progress: JobProgress[];
  log: JobLogLine[];
  snapshot: { header: SnapshotHeader; data: Float32Array } | null;
  done: JobDone | null;
}

type Action =
  | { type: "message"; message: JobMessage }
  | { type: "snapshot"; header: SnapshotHeader; data: Float32Array }
  | { type: "closed"; clean: boolean }
  | { type: "reset" };

export const initialJobState: JobState = {
  connection: "connecting",
  started: null,
  progress: [],
  log: [],
  snapshot: null,
  done: null,
};

const capLog = (log: JobLogLine[]) => (log.length > MAX_LOG ? log.slice(-MAX_LOG) : log);

export function jobReducer(state: JobState, action: Action): JobState {
  switch (action.type) {
    case "reset":
      return initialJobState;
    case "snapshot":
      return { ...state, snapshot: { header: action.header, data: action.data } };
    case "closed":
      return action.clean || state.done ? state : { ...state, connection: "lost" };
    case "message": {
      const m = action.message;
      switch (m.type) {
        case "started":
          return { ...state, connection: "open", started: m };
        case "history":
          return { ...state, connection: "open", progress: m.progress, log: capLog(m.log) };
        case "progress":
          return { ...state, connection: "open", progress: [...state.progress, m] };
        case "log":
          return { ...state, log: capLog([...state.log, m]) };
        case "done":
          return { ...state, done: m };
      }
    }
  }
  return state;
}

/**
 * Follows one job over its WebSocket: replayed history first, then live messages.
 * Bumping `attempt` reconnects (the server replays the history again).
 */
export function useJob(jobId: string | null | undefined, attempt = 0): JobState {
  const token = useApiToken();
  const [state, dispatch] = useReducer(jobReducer, initialJobState);
  useEffect(() => {
    dispatch({ type: "reset" });
    if (!jobId) return;
    return openJobSocket(jobId, token, {
      onMessage: (message) => dispatch({ type: "message", message }),
      onSnapshot: (header, data) => dispatch({ type: "snapshot", header, data }),
      onClose: (clean) => dispatch({ type: "closed", clean }),
    });
  }, [jobId, token, attempt]);
  return state;
}
