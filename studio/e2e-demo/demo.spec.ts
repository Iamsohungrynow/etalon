// The static demo (docs/plan-demo.md): recorded answers only, no server behind it.
import { test as base, expect, type Page } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:8792";
/** The build's base path, as in playwright.demo.config.ts ("/studio/" for the site). */
const BASE = process.env.ETALON_BASE ?? "/";
const at = (path = "") => `${BASE}${path}`;

/** Fails a test on any request off this origin or any console error. */
const test = base.extend({
  page: async ({ page }, use) => {
    const offsite: string[] = [];
    const errors: string[] = [];
    page.on("request", (r) => {
      const url = r.url();
      if (!url.startsWith("data:") && !url.startsWith("blob:") && !url.startsWith(`${ORIGIN}/`)) offsite.push(url);
    });
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    page.on("pageerror", (e) => errors.push(String(e)));
    await use(page);
    expect(offsite, "requests that left the site").toEqual([]);
    expect(errors, "console errors").toEqual([]);
  },
});

/** A finished row links to its Results; go to its Setup instead. */
async function openSetup(page: Page, title: string) {
  await page.goto(at());
  const href = await page.getByRole("link", { name: title, exact: true }).getAttribute("href");
  const id = /\/sim\/([0-9a-f]{12})\//.exec(href ?? "")?.[1];
  expect(id, title).toBeTruthy();
  await page.goto(at(`sim/${id}/setup`));
}

const TEMPLATES = [
  ["Strip waveguide", "strip_waveguide.py"],
  ["Sharp bend", "sharp_bend.py"],
  ["Photonic-crystal waveguide", "phc_waveguide.py"],
  ["Vacuum pulse", "vacuum_pulse.py"],
] as const;

test("Demo: the workspace shows the banner, the four recorded templates, and no create", async ({ page }) => {
  await page.goto(at());
  await expect(page.getByTestId("demo-banner")).toContainText("replayed in your browser");
  for (const [title, file] of TEMPLATES) {
    const row = page.getByRole("row").filter({ has: page.getByText(file, { exact: true }) });
    await expect(row.getByRole("link", { name: title, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "New from template" })).toBeDisabled();
});

test("Demo: Setup draws the recorded structure and the solver's permittivity", async ({ page }) => {
  await openSetup(page, "Photonic-crystal waveguide");
  await expect(page.getByRole("heading", { name: "Photonic-crystal waveguide" })).toBeVisible();
  await expect(page).toHaveTitle("Photonic-crystal waveguide · Etalon Studio");
  const viewport = page.getByRole("img", { name: "The simulation in 3D" });
  await expect(viewport).toBeVisible({ timeout: 30_000 });
  await expect.poll(async () => (await viewport.screenshot()).length, { timeout: 10_000 }).toBeGreaterThan(30_000);
  await page.getByRole("radio", { name: "Slice" }).click();
  const canvas = page.getByRole("img", { name: /Relative permittivity on the simulated plane/ });
  const box = await canvas.boundingBox();
  if (!box) throw new Error("slice canvas has no box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  const readout = page.getByText(/εr \d/);
  await expect(readout).toBeVisible();
  const value = Number(/εr ([\d.]+)/.exec((await readout.textContent()) ?? "")?.[1]);
  expect(value).toBeCloseTo(3.476 ** 2, 1); // silicon along the line defect
});

test("Demo: Run replays the recorded run to the end and opens its results", async ({ page }) => {
  await openSetup(page, "Strip waveguide");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page).toHaveURL(/\/run$/);
  await expect(page.getByRole("button", { name: "Cancel" })).toBeDisabled();
  await expect(page.getByRole("img", { name: /Live Hz field/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("The run finished.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("cuda:0 · NVIDIA GeForce RTX 4060 Ti", { exact: true })).toBeVisible();
  await expect(page.getByRole("log", { name: "Run log" })).not.toBeEmpty();
  await page.getByRole("link", { name: "Open results" }).click();
  await expect(page).toHaveURL(/\/results$/);
  await expect(page.getByRole("img", { name: /on monitor/ })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Spectra" }).click();
  await page.getByRole("radio", { name: "Table" }).click();
  await expect(page.getByRole("table").first()).toContainText("1.55");
});

test.describe("Demo in Chinese", () => {
  test.use({ locale: "zh-CN" });

  test("the banner follows the browser's language", async ({ page }) => {
    await page.goto(at("settings"));
    await expect(page.getByTestId("demo-banner")).toContainText("在浏览器中回放");
  });
});
