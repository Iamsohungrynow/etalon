// P7, P8: simulation routes for scripts that cannot run, unknown addresses, an ended session.
import { ORIGIN } from "./env";
import { expect, open, test, workspaceRows } from "./guards";

test("P7: a script without a Simulation: Setup explains, Run is idle, Results are empty", async ({ page, request }) => {
  const id = (await workspaceRows(request)).find((r) => r.path === "rings/ring_r10_g200.py")?.id;
  await open(page, `/sim/${id}/setup`);
  await expect(page.getByRole("heading", { name: "ring_r10_g200.py" })).toBeVisible();
  await expect(page.getByText("This script defines no etalon Simulation")).toBeVisible();
  await page.getByRole("navigation", { name: "Simulation views" }).getByRole("link", { name: "Run" }).click();
  await expect(page.getByRole("heading", { name: "This simulation is not running" })).toBeVisible();
  await page.getByRole("navigation", { name: "Simulation views" }).getByRole("link", { name: "Results" }).click();
  await expect(page.getByRole("heading", { name: "No results yet" })).toBeVisible();
});

test("P7: Mode Solver and Validation have their routes, not yet their navigation", async ({ page }) => {
  for (const [path, title] of [["/modes", "Mode Solver"], ["/validation", "Validation"]]) {
    await open(page, path);
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.getByText("is not in this version yet")).toBeVisible();
  }
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link")).toHaveText(["Workspace", "Settings"]);
});

test("P7: an unknown simulation id and an unknown page", async ({ page }) => {
  await open(page, "/sim/000000000000/results");
  await expect(page.getByRole("alert")).toContainText("No simulation with this id in the workspace.");
  await open(page, "/no/such/page");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await expect(page.getByText("/no/such/page")).toBeVisible();
  await page.getByRole("link", { name: "Back to Workspace" }).click();
  await expect(page).toHaveURL(`${ORIGIN}/`);
});

test.describe("P8: without a token", () => {
  test.use({ allowConsole: [/status of 401/] });

  test("shows the session-ended screen with the way back", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "This Studio session has ended" })).toBeVisible();
    await expect(page.getByText("etalon studio", { exact: true })).toBeVisible();
  });
});
