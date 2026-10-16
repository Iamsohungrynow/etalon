// U1 Setup: the structure tree, the 3D view, the solver's own permittivity slice, errors.
import type { Page } from "@playwright/test";
import { expect, open, test, workspaceRows } from "./guards";

async function setupOf(
  page: Page,
  request: Parameters<typeof workspaceRows>[0],
  path: string,
) {
  const id = (await workspaceRows(request)).find((r) => r.path === path)?.id;
  expect(id, path).toBeTruthy();
  await open(page, `/sim/${id}/setup`);
  return id ?? "";
}

/** Hover the centre of the slice canvas: the grid is symmetric, so that is (0, 0). */
async function epsilonAtCentre(page: Page): Promise<number> {
  const canvas = page.getByRole("img", {
    name: /Relative permittivity on the simulated plane/,
  });
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("slice canvas has no box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  const readout = page.getByText(/εr \d/);
  await expect(readout).toBeVisible();
  const match = /εr ([\d.]+)/.exec((await readout.textContent()) ?? "");
  return Number(match?.[1]);
}

test("Setup: the photonic-crystal template shows its tree, 3D view, estimate and slice", async ({
  page,
  request,
}) => {
  await setupOf(page, request, "phc_waveguide.py");
  await expect(page.getByText("Building simulation…")).toHaveCount(0, {
    timeout: 30_000,
  });
  const tree = page.getByRole("tree", { name: "Structure" });
  await expect(
    tree.getByRole("treeitem", { name: /Structures/ }),
  ).toBeVisible();
  await expect(tree.getByRole("treeitem", { name: /dipole/ })).toBeVisible();
  await expect(
    page.getByRole("img", { name: "The simulation in 3D" }),
  ).toBeVisible();
  await expect(page.getByText("Estimate")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run" })).toBeEnabled();

  await tree.getByText("dipole", { exact: true }).click();
  await expect(page.getByText("Component")).toBeVisible();
  await expect(page.getByText("1.55 µm")).toBeVisible();

  await page.getByRole("radio", { name: "Slice" }).click();
  // The line defect runs along y = 0: solid silicon there.
  expect(await epsilonAtCentre(page)).toBeCloseTo(3.476 ** 2, 1);
});

test("Setup: a misplaced strip is visibly misplaced in the slice", async ({
  page,
  request,
}) => {
  await setupOf(page, request, "misplaced_strip.py");
  await page.getByRole("radio", { name: "Slice" }).click();
  // The script meant the strip to run along y = 0; the solver sees SiO2 there.
  expect(await epsilonAtCentre(page)).toBeCloseTo(1.444 ** 2, 1);
});

test.describe("Setup: a failing script", () => {
  test.use({ allowConsole: [/status of 422/] }); // the spec request answers 422 by design

  test("shows its traceback with the line", async ({ page, request }) => {
    await setupOf(page, request, "broken_script.py");
    const alert = page.getByRole("alert");
    await expect(alert).toContainText("The script failed");
    await expect(alert).toContainText("at line 12");
    await expect(alert.getByText("Traceback", { exact: true })).toBeVisible();
    await expect(
      alert.getByRole("button", { name: "Open in editor" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Run" })).toBeDisabled();
  });
});
