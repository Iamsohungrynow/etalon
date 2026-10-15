/**
 * The typed API client. Every type comes from schema.ts, which openapi-typescript
 * generates from the server's OpenAPI schema (`pnpm gen:api`); none is written by hand.
 */
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const TOKEN_HEADER = "X-Etalon-Token";

export type Api = ReturnType<typeof createClient<paths>>;
export type Settings = components["schemas"]["StudioSettings"];
export type Workspace = components["schemas"]["Workspace"];
export type SimulationRow = components["schemas"]["SimulationRow"];
export type SystemInfo = components["schemas"]["SystemInfo"];
export type Device = components["schemas"]["Device"];
export type SimulationStatus = SimulationRow["status"];

export function createApi(token: string | null, fetchImpl?: typeof fetch): Api {
  return createClient<paths>({
    baseUrl: globalThis.location?.origin ?? "",
    headers: token ? { [TOKEN_HEADER]: token } : {},
    ...(fetchImpl ? { fetch: fetchImpl } : {}),
  });
}

/** The server ended this session's access: no token, or one from an earlier install. */
export class SessionEndedError extends Error {
  constructor() {
    super("Studio session ended (401)");
    this.name = "SessionEndedError";
  }
}

/** The server could not be reached at all (stopped, or the port changed). */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super(`Studio server unreachable: ${String(cause)}`);
    this.name = "NetworkError";
  }
}

interface ValidationIssue {
  type: string;
  loc: (string | number)[];
  msg: string;
}

/** The server answered with an error status. */
export class ServerError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    super(`Studio server error ${status}`);
    this.name = "ServerError";
    this.status = status;
    this.body = body;
  }

  /** `code` of an ApiError body (e.g. "workspace_missing"). */
  get code(): string | undefined {
    const body = this.body as { code?: unknown } | null;
    return typeof body?.code === "string" ? body.code : undefined;
  }

  /** The validation issues of a 422 answer. */
  get issues(): ValidationIssue[] {
    const body = this.body as { detail?: unknown } | null;
    return Array.isArray(body?.detail) ? (body.detail as ValidationIssue[]) : [];
  }
}

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Turns an openapi-fetch call into data or one of the errors above. */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await call;
  } catch (cause) {
    throw new NetworkError(cause);
  }
  if (result.response.status === 401) throw new SessionEndedError();
  if (!result.response.ok || result.data === undefined) {
    throw new ServerError(result.response.status, result.error);
  }
  return result.data;
}
