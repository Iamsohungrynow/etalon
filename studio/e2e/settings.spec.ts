// P4, P5, P6: Settings, theme and language across every route.
import { latinOutsideTerms } from "../src/i18n/latinTerms";
import { DEFAULT_SETTINGS, WS50 } from "./env";
import { expect, open, putSettings, test, workspaceRows } from "./guards";
import type { Page } from "@playwright/test";

const DARK_BG = "rgb(14, 16, 19)";
const PAPER_BG = "rgb(242, 240, 228)";
const background = (page: Page) => page.evaluate(() => getComputedStyle(document.body).backgroundColor);

test("P6: Settings shows every section; the backend lists the devices; the folder switches", async ({ page }) => {
  await open(page, "/settings");
  for (const name of ["Backend", "Workspace folder", "Language", "Theme", "Length units", "Live field snapshots", "Privacy", "About"]) {
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByText("Studio makes no network requests.", { exact: false })).toBeVisible();
  const detecting = page.getByText("Detecting GPU…");
  await expect(detecting).toHaveCount(0, { timeout: 30_000 });
  await page.getByRole("combobox", { name: "Backend" }).click();
  const options = await page.getByRole("option").allTextContents();
  expect(options.slice(0, 2)).toEqual(["Auto", "CPU"]);
  const devices = await page.evaluate(() => fetch("/api/system", { headers: { "X-Etalon-Token": localStorage.getItem("etalon.studio.token") ?? "" } }).then((r) => r.json()));
  expect(options.length).toBe(2 + (devices as { devices: unknown[] }).devices.length);
  await page.keyboard.press("Escape");

  const field = page.getByRole("textbox", { name: "Folder path" });
  await field.fill(WS50);
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("button", { name: "Apply" })).toBeDisabled();
  await page.getByRole("link", { name: "Workspace", exact: true }).click();
  await expect(page.getByTestId("workspace-count")).toHaveText("50 simulations");
});

test.describe("P6: a folder that does not exist", () => {
  test.use({ allowConsole: [/status of 422/] });

  test("is refused inline, and nothing changes", async ({ page }) => {
    await open(page, "/settings");
    const field = page.getByRole("textbox", { name: "Folder path" });
    await field.fill(`${WS50}-missing`);
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("This folder does not exist.")).toBeVisible();
    await expect(field).toHaveAttribute("aria-invalid", "true");
    await page.getByRole("link", { name: "Workspace", exact: true }).click();
    await expect(page.getByTestId("workspace-count")).toHaveText("10 simulations");
  });
});

test("P5: dark by default; Light is paper and survives a reload; System follows the OS", async ({ page, request }) => {
  await open(page, "/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await background(page)).toBe(DARK_BG);
  await expect(page.getByTestId("spectrum-stripe")).toBeVisible();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: "Light" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(() => background(page)).toBe(PAPER_BG);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light"); // set by the server, before any script
  expect(await background(page)).toBe(PAPER_BG);

  await putSettings(request, { ...DEFAULT_SETTINGS, theme: "system" });
  await page.emulateMedia({ colorScheme: "light" });
  await page.reload();
  await expect.poll(() => background(page)).toBe(PAPER_BG);
  await page.emulateMedia({ colorScheme: "dark" });
  await expect.poll(() => background(page)).toBe(DARK_BG);
});

/**
 * Visible text and labels outside translate="no" that still contain Latin words. `data`
 * names values that may appear where markup cannot mark them, e.g. a script name in the
 * tab title.
 */
async function untranslated(page: Page, data: string[] = []): Promise<string[]> {
  const texts = await page.evaluate(() => {
    const out: string[] = [document.title];
    const skip = (el: Element | null) =>
      !el || el.closest('[translate="no"], [aria-hidden="true"], script, style') !== null;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent?.trim();
      if (text && !skip(node.parentElement)) out.push(text);
    }
    for (const el of document.querySelectorAll("[aria-label], [title], [placeholder]")) {
      if (skip(el)) continue;
      for (const name of ["aria-label", "title", "placeholder"]) {
        const value = el.getAttribute(name);
        if (value) out.push(value);
      }
    }
    return out;
  });
  return texts
    .map((text) => data.reduce((rest, value) => rest.split(value).join(""), text))
    .filter((text) => latinOutsideTerms(text) !== "");
}

test("P4: after switching to 简体中文, every route shows only Chinese UI text", async ({ page, request }) => {
  await open(page, "/settings");
  await page.getByRole("radio", { name: "简体中文" }).click();
  await expect(page.getByRole("heading", { name: "设置", exact: true })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");

  const rows = await workspaceRows(request);
  const id = rows.find((r) => r.path === "straight_wg.py")?.id ?? "";
  const routes: [string, string][] = [
    ["/", "工作区"],
    ["/settings", "设置"],
    [`/sim/${id}/setup`, "Straight strip waveguide"],
    [`/sim/${id}/run`, "Straight strip waveguide"],
    [`/sim/${id}/results`, "Straight strip waveguide"],
    ["/modes", "模式求解器"],
    ["/validation", "验证"],
    ["/sim/000000000000/setup", "工作区中没有此 ID 的仿真。"],
    ["/no/such/page", "未找到页面"],
  ];
  for (const [path, heading] of routes) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, exact: true }).first()).toBeVisible();
    await expect(page.getByText("正在检测 GPU…")).toHaveCount(0, { timeout: 30_000 });
    // The script's path and title are data, as written in the script.
    expect(await untranslated(page, ["straight_wg.py", "Straight strip waveguide"]), path).toEqual([]);
  }
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");

  await page.goto("/settings");
  await page.getByRole("radio", { name: "English" }).click();
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
});
