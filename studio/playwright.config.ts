/**
 * Playwright smoke tests (plan-u0 §6, P1–P9) against the built SPA, served by the real
 * `etalon studio` on the fixture workspace. Run `pnpm build` first; the tests share one
 * server (and its settings), so they run one at a time.
 */
import { rmSync } from "node:fs";
import { defineConfig, devices } from "@playwright/test";
import { CONFIG_DIR, FIXTURE, ORIGIN, PORT, PYTHON, REPO_ROOT, RUN_WS, TOKEN, makeWorkspace50 } from "./e2e/env";

if (process.env.TEST_WORKER_INDEX === undefined) {
  // Main process only: start from fresh settings, and make sure the 50-script workspace exists.
  rmSync(CONFIG_DIR, { recursive: true, force: true });
  // Earlier runs' folders; a file still held open on Windows is left for next time.
  try {
    rmSync(RUN_WS, { recursive: true, force: true, maxRetries: 2 });
  } catch {
    // Each Run test uses a fresh folder inside RUN_WS anyway.
  }
  makeWorkspace50();
}

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: ORIGIN,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
        // The Setup viewport needs WebGL; headless Chromium provides it in software.
        launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] },
      },
    },
  ],
  webServer: {
    command: `"${PYTHON}" -m etalon.cli studio "${FIXTURE}" --port ${PORT} --no-browser`,
    cwd: REPO_ROOT,
    url: `${ORIGIN}/`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { ETALON_CONFIG_DIR: CONFIG_DIR, ETALON_STUDIO_TOKEN: TOKEN },
    stdout: "pipe",
    stderr: "pipe",
  },
});
