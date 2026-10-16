// P1, P2, P3, P9: the Workspace route.
import { spawn } from "node:child_process";
import { rmSync } from "node:fs";
import { DEFAULT_SETTINGS, PYTHON, REPO_ROOT, TIMING_CONFIG_DIR, TIMING_PORT, TOKEN, WS50 } from "./env";
import { expect, open, putSettings, test, workspaceRows } from "./guards";

/** [path, title]: sorted by path; the title is the docstring's first line up to ":". */
const LISTED: [path: string, title: string][] = [
  ["bend_euler.py", "Euler bend, 90 degrees"],
  ["broken_script.py", "Broken script"],
  ["broken_status.py", "Corrupt status file"],
  ["dc_gap200.py", "Directional coupler, gap 200 nm"],
  ["misplaced_strip.py", "Misplaced strip"],
  ["mmi_1x2_sweep.py", "MMI 1x2 length sweep"],
  ["phc_waveguide.py", "Photonic-crystal waveguide"],
  ["rings/ring_r10_g180.py", "Add-drop ring, radius 10 um, gap 180 nm"],
  ["rings/ring_r10_g200.py", "Add-drop ring, radius 10 um, gap 200 nm"],
  ["straight_wg.py", "Straight strip waveguide"],
];

test("P1: the fixture workspace lists every status, and skips what it should", async ({ page }) => {
  await open(page, "/");
  await expect(page.getByTestId("workspace-count")).toHaveText("10 simulations");
  const titles = await page.getByRole("table").getByRole("link").allTextContents();
  expect(titles).toEqual(LISTED.map(([, title]) => title));
  // Each title leads its row; the script's path stays visible under it.
  const row = (path: string) => page.getByRole("row").filter({ has: page.getByText(path, { exact: true }) });
  for (const [path, title] of LISTED) {
    await expect(row(path).getByRole("link", { name: title, exact: true })).toBeVisible();
  }
  await expect(row("straight_wg.py")).toContainText("done");
  await expect(row("straight_wg.py")).not.toContainText("stale");
  await expect(row("rings/ring_r10_g200.py")).toContainText("stale");
  await expect(row("rings/ring_r10_g180.py")).toContainText("running");
  await expect(row("rings/ring_r10_g180.py")).toContainText("11 k / 26.4 k");
  await expect(row("mmi_1x2_sweep.py")).toContainText("draft");
  await expect(row("dc_gap200.py")).toContainText("failed");
  await expect(row("bend_euler.py")).toContainText("cancelled");
  await expect(row("bend_euler.py")).toContainText("1h04m");
  await expect(row("broken_status.py")).toContainText("unknown");
  for (const skipped of ["_private_helper.py", "secret.py", "site.py", "notes.txt"]) {
    await expect(page.getByText(skipped)).toHaveCount(0);
  }
  await expect(page).toHaveURL(/\/$/); // the token left the address bar
  await expect(page).toHaveTitle("Workspace · Etalon Studio");
});

test("P2: a 50-script workspace lists all 50; rows lead to their screens", async ({ page, request }) => {
  await putSettings(request, { ...DEFAULT_SETTINGS, workspace: WS50 });
  await open(page, "/");
  await expect(page.getByTestId("workspace-count")).toHaveText("50 simulations");
  await expect(page.getByRole("table")).toHaveAttribute("aria-rowcount", "51");
  await page.getByTestId("table-scroll").evaluate((el) => el.scrollTo(0, el.scrollHeight));
  const last = page.getByRole("link", { name: "Generated e2e script 49.", exact: true });
  await expect(last).toBeVisible();
  await expect(page.getByText("group_4/device_49.py", { exact: true })).toBeVisible();
  await last.click();
  await expect(page).toHaveURL(/\/sim\/[0-9a-f]{12}\/results$/);
  await expect(page.getByRole("heading", { name: "Generated e2e script 49." })).toBeVisible();
  await expect(page).toHaveTitle("Generated e2e script 49. · Etalon Studio");
  await page.goBack();
  await page.getByRole("link", { name: "Generated e2e script 0.", exact: true }).click();
  await expect(page).toHaveURL(/\/sim\/[0-9a-f]{12}\/setup$/);
});

test.describe("P3: opening time", () => {
  test.use({ allowedOrigins: [`http://127.0.0.1:${TIMING_PORT}`] });

  test("etalon studio → 50 rows on screen in under 2 s", async ({ page }) => {
    rmSync(TIMING_CONFIG_DIR, { recursive: true, force: true });
    const origin = `http://127.0.0.1:${TIMING_PORT}`;
    const started = performance.now();
    const studio = spawn(
      PYTHON,
      ["-m", "etalon.cli", "studio", WS50, "--port", String(TIMING_PORT), "--no-browser"],
      {
        cwd: REPO_ROOT,
        env: { ...process.env, ETALON_CONFIG_DIR: TIMING_CONFIG_DIR, ETALON_STUDIO_TOKEN: TOKEN },
        stdio: "ignore",
      },
    );
    try {
      for (;;) {
        const up = await fetch(`${origin}/`).then((r) => r.ok, () => false);
        if (up) break;
        if (performance.now() - started > 30_000) throw new Error("Studio did not start in 30 s");
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      const serving = performance.now() - started;
      await page.goto(`${origin}/?token=${TOKEN}`);
      await expect(page.getByTestId("workspace-count")).toHaveText("50 simulations");
      await expect(page.getByRole("link", { name: "Generated e2e script 0.", exact: true })).toBeVisible();
      const opened = performance.now() - started;
      test.info().annotations.push({
        type: "open-time",
        description: `server answering after ${serving.toFixed(0)} ms; 50 rows on screen after ${opened.toFixed(0)} ms`,
      });
      console.log(`P3 open time: server ${serving.toFixed(0)} ms, table ${opened.toFixed(0)} ms`);
      expect(opened).toBeLessThan(2000);
    } finally {
      studio.kill();
    }
  });
});

test("P9: the keyboard reaches navigation, filter and rows; Enter opens a row", async ({ page, request }) => {
  await open(page, "/");
  await expect(page.getByTestId("workspace-count")).toHaveText("10 simulations");
  const visited: string[] = [];
  for (let i = 0; i < 20; i++) {
    await page.keyboard.press("Tab");
    const label = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return el ? `${el.tagName.toLowerCase()}:${el.getAttribute("aria-label") ?? el.textContent?.trim() ?? ""}` : "";
    });
    visited.push(label);
    if (label === "a:Euler bend, 90 degrees") break;
  }
  expect(visited).toContain("a:Workspace");
  expect(visited).toContain("a:Settings");
  expect(visited).toContain("input:");
  expect(visited.at(-1)).toBe("a:Euler bend, 90 degrees"); // the first row, by its title
  const ring = await page.evaluate(() => getComputedStyle(document.activeElement?.closest("[role=row]") as Element).outlineStyle);
  expect(ring).toBe("solid");
  const id = (await workspaceRows(request)).find((r) => r.path === "bend_euler.py")?.id;
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/sim/${id}/results$`));
});
