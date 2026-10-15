/**
 * The `test` every spec uses. Around each test it
 * - resets the server's settings (English, dark, the fixture workspace),
 * - fails the test if the page requested anything outside 127.0.0.1:<port>
 *   ("nothing leaves the machine"),
 * - fails the test on any console error or uncaught exception, unless the test
 *   declares it expects one (`test.use({ allowConsole: [/401/] })`).
 */
import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { DEFAULT_SETTINGS, ORIGIN, TOKEN } from "./env";

interface GuardOptions {
  allowConsole: RegExp[];
  allowedOrigins: string[];
}

export const test = base.extend<GuardOptions>({
  allowConsole: [[], { option: true }],
  allowedOrigins: [[ORIGIN], { option: true }],
  page: async ({ page, request, allowConsole, allowedOrigins }, use) => {
    await putSettings(request, DEFAULT_SETTINGS);
    const offsite: string[] = [];
    const errors: string[] = [];
    page.on("request", (r) => {
      const url = r.url();
      if (url.startsWith("data:") || url.startsWith("blob:")) return;
      if (!allowedOrigins.some((origin) => url.startsWith(`${origin}/`))) offsite.push(url);
    });
    page.on("console", (message) => {
      if (message.type() !== "error") return;
      if (!allowConsole.some((pattern) => pattern.test(message.text()))) errors.push(message.text());
    });
    page.on("pageerror", (error) => errors.push(String(error)));
    await use(page);
    expect(offsite, "requests that left 127.0.0.1").toEqual([]);
    expect(errors, "console errors").toEqual([]);
  },
});

export { expect };

/** Open a Studio path the way the CLI link does: with ?token= the first time. */
export async function open(page: Page, path = "/"): Promise<void> {
  await page.goto(`${path}${path.includes("?") ? "&" : "?"}token=${TOKEN}`);
}

export async function putSettings(
  request: APIRequestContext,
  settings: Record<string, unknown>,
): Promise<void> {
  const response = await request.put(`${ORIGIN}/api/settings`, {
    headers: { "X-Etalon-Token": TOKEN },
    data: settings,
  });
  expect(response.status(), await response.text()).toBe(200);
}

export async function workspaceRows(
  request: APIRequestContext,
): Promise<{ id: string; path: string; status: string }[]> {
  const response = await request.get(`${ORIGIN}/api/workspace`, {
    headers: { "X-Etalon-Token": TOKEN },
  });
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { simulations: { id: string; path: string; status: string }[] })
    .simulations;
}
