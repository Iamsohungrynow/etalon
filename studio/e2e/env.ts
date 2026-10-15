/** Paths, ports and the token shared by playwright.config.ts and the specs. */
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const STUDIO_DIR = fileURLToPath(new URL("..", import.meta.url));
export const REPO_ROOT = join(STUDIO_DIR, "..");
export const PYTHON =
  process.env.ETALON_PYTHON ??
  join(REPO_ROOT, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

export const TOKEN = "e2e-token-0123456789";
export const PORT = 8790;
export const ORIGIN = `http://127.0.0.1:${PORT}`;
/** P3 starts its own Studio here, to time it from the command to the table. */
export const TIMING_PORT = 8791;

export const FIXTURE = join(STUDIO_DIR, "e2e", "fixtures", "workspace");
export const E2E_ROOT = join(tmpdir(), "etalon-e2e");
export const CONFIG_DIR = join(E2E_ROOT, "config");
export const TIMING_CONFIG_DIR = join(E2E_ROOT, "config-timing");
export const WS50 = join(E2E_ROOT, "ws50");

export const DEFAULT_SETTINGS = {
  backend: "auto",
  language: "en",
  theme: "dark",
  units: "um",
  live_snapshots: false,
  workspace: FIXTURE,
} as const;

const WS50_VERSION = "1";

function write(path: string, text: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text);
}

/** A workspace of 50 scripts in 5 folders; every other one has a finished run. Idempotent. */
export function makeWorkspace50(folder = WS50): string {
  const marker = join(folder, ".etalon", "generated");
  if (existsSync(marker) && readFileSync(marker, "utf-8") === WS50_VERSION) return folder;
  rmSync(folder, { recursive: true, force: true });
  for (let i = 0; i < 50; i++) {
    const script = join(folder, `group_${i % 5}`, `device_${String(i).padStart(2, "0")}.py`);
    const text = `"""Generated e2e script ${i}."""\n\nimport etalon as et\n`;
    write(script, text);
    if (i % 2) {
      const status = {
        status: "done",
        finished_at: "2026-10-15T06:00:00Z",
        backend: "cuda:0",
        cells: 1_000_000 * (i + 1),
        wall_time_s: 60 + i,
        script_sha256: createHash("sha256").update(text).digest("hex"),
      };
      write(join(dirname(script), ".etalon", `device_${String(i).padStart(2, "0")}.py`, "status.json"), JSON.stringify(status));
    }
  }
  write(marker, WS50_VERSION);
  return folder;
}
