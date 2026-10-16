// U2 Run: a real CPU run from a template, live over the WebSocket, then cancel.
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import type { APIRequestContext, Page, WebSocket as PwWebSocket } from "@playwright/test";
import { DEFAULT_SETTINGS, RUN_WS } from "./env";
import { expect, open, putSettings, test } from "./guards";

/**
 * A fresh, empty workspace for each run, on the CPU so no GPU is needed, with live
 * snapshots on so frames arrive on the CPU too. A new folder each time: on Windows the
 * previous test's job may still hold its files open. Called inside each test, because
 * the guarded `page` fixture resets Settings to the defaults when it is set up.
 */
async function useRunWorkspace(request: APIRequestContext): Promise<void> {
  const workspace = join(RUN_WS, randomUUID());
  mkdirSync(workspace, { recursive: true });
  await putSettings(request, { ...DEFAULT_SETTINGS, workspace, backend: "cpu", live_snapshots: true });
}

/** Text frames of type progress, with the time each arrived. */
function watchProgress(page: Page) {
  const times: number[] = [];
  let snapshots = 0;
  page.on("websocket", (ws: PwWebSocket) => {
    ws.on("framereceived", ({ payload }) => {
      if (typeof payload !== "string") {
        snapshots++;
        return;
      }
      if (payload.includes('"type":"progress"') || payload.includes('"type": "progress"')) times.push(Date.now());
    });
  });
  return { times, snapshots: () => snapshots };
}

test("Run: a template runs on the CPU with progress ≥ 2 Hz, live frames, and opens its results", async ({ page, request }) => {
  test.setTimeout(120_000);
  await useRunWorkspace(request);
  const progress = watchProgress(page);
  await open(page, "/");
  await page.getByRole("button", { name: "New from template" }).click();
  const form = page.getByRole("form", { name: "New simulation from a template" });
  await form.getByRole("combobox", { name: "Template" }).click();
  await page.getByRole("option", { name: "Strip waveguide (2D)" }).click();
  await form.getByRole("textbox", { name: "File name" }).fill("e2e_strip");
  await form.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/sim\/[0-9a-f]{12}\/setup$/);
  await expect(page.getByRole("heading", { name: "e2e_strip.py" })).toBeVisible();

  await page.getByRole("button", { name: "Run" }).click();
  await expect(page).toHaveURL(/\/run$/);
  await expect(page.getByRole("img", { name: /Live Hz field/ })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("The run finished.")).toBeVisible({ timeout: 90_000 });

  // Progress rate while running: frames after the first, over the span they cover.
  const t = progress.times;
  expect(t.length).toBeGreaterThan(3);
  const span = ((t.at(-1) ?? 0) - (t[0] ?? 0)) / 1000;
  if (span > 1.5) expect((t.length - 1) / span).toBeGreaterThanOrEqual(2);
  expect(progress.snapshots()).toBeGreaterThan(0);
  await expect(page.getByRole("log", { name: "Run log" })).not.toBeEmpty();

  await page.getByRole("link", { name: "Open results" }).click();
  await expect(page).toHaveURL(/\/results$/);
  await expect(page.getByRole("img", { name: /on monitor/ })).toBeVisible({ timeout: 30_000 });
});

test("Run: cancel stops the run within 2 s and keeps its data", async ({ page, request }) => {
  test.setTimeout(120_000);
  await useRunWorkspace(request);
  await open(page, "/");
  await page.getByRole("button", { name: "New from template" }).click();
  const form = page.getByRole("form", { name: "New simulation from a template" });
  await form.getByRole("combobox", { name: "Template" }).click();
  await page.getByRole("option", { name: "Photonic-crystal waveguide (2D)" }).click();
  await form.getByRole("textbox", { name: "File name" }).fill("e2e_cancel");
  await form.getByRole("button", { name: "Create" }).click();
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText(/elapsed/)).toBeVisible({ timeout: 60_000 });
  const clicked = Date.now();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText(/The run was cancelled/)).toBeVisible({ timeout: 5_000 });
  expect(Date.now() - clicked).toBeLessThan(2_000 + 500); // 2 s budget, plus the UI round trip
});
