// U3 (fields part): the recorded photonic-crystal run, read without a GPU.
import type { APIRequestContext, Page } from "@playwright/test";
import { expect, fetchArray, open, test, workspaceRows } from "./guards";

async function openResults(page: Page, request: APIRequestContext) {
  const id = (await workspaceRows(request)).find((r) => r.path === "phc_waveguide.py")?.id;
  await open(page, `/sim/${id}/results`);
}

test("Results: the recorded run shows its metadata and the field, and exports a PNG", async ({ page, request }) => {
  await openResults(page, request);
  await expect(page.getByText("Finished")).toBeVisible();
  await expect(page.getByText(/AMD Ryzen|cpu/).first()).toBeVisible();
  const canvas = page.getByRole("img", { name: "Hz on monitor field" });
  await expect(canvas).toBeVisible();

  // The hover readout agrees with the stored array at the node under the cursor.
  const row = (await workspaceRows(request)).find((r) => r.path === "phc_waveguide.py");
  const field = await fetchArray(
    request,
    `/api/results/${encodeURIComponent(row?.last_result_id ?? "")}/fields/field?component=Hz&quantity=abs&wavelength_index=1`,
  );
  const [nx, ny] = field.header.shape;
  const [x0, x1, y0, y1] = field.header.extent;
  const box = await canvas.boundingBox();
  if (!box) throw new Error("no canvas box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  const readout = page.getByText(/µm · [-\d.e+]+$/);
  await expect(readout).toBeVisible();
  const text = (await readout.textContent()) ?? "";
  const [, xs, ys, vs] = /x ([-\d.]+) · y ([-\d.]+) µm · ([-\d.e+]+)/.exec(text) ?? [];
  const i = Math.round(((Number(xs) - x0) / (x1 - x0)) * (nx - 1));
  const j = Math.round(((Number(ys) - y0) / (y1 - y0)) * (ny - 1));
  const stored = field.data[i * ny + j] ?? NaN;
  expect(Math.abs(Number(vs) - stored)).toBeLessThanOrEqual(Math.abs(stored) * 1e-4 + 1e-12);

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PNG" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.png$/);
});

test("Results: point spectra as a table and CSV; S-parameters wait for M2", async ({ page, request }) => {
  await openResults(page, request);
  await page.getByRole("tab", { name: "Spectra" }).click();
  await page.getByRole("radio", { name: "Table" }).click();
  await expect(page.getByRole("table").first()).toContainText("1.55");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.csv$/);
  await expect(page.getByRole("tab", { name: "S-parameters" })).toBeDisabled();
});
