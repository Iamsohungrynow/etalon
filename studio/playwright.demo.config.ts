/**
 * Playwright smoke test of the static demo build (docs/plan-demo.md), served by
 * `vite preview` exactly as Netlify serves it: no Studio server, no Python, no GPU.
 * Run `pnpm build:demo` first (it needs studio/demo-data/ from record_demo.py), with the
 * same ETALON_BASE as here: the site's build serves it under /studio/.
 */
import { defineConfig, devices } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:8792";
const BASE = process.env.ETALON_BASE ?? "/";

export default defineConfig({
  testDir: "e2e-demo",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: [["list"]],
  use: { baseURL: ORIGIN, trace: "retain-on-failure" },
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
    command: "pnpm exec vite preview --mode demo",
    url: `${ORIGIN}${BASE}`,
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
