// The kitchen sink renders every component in both themes, with no console error.
import { DEFAULT_SETTINGS } from "./env";
import { expect, open, putSettings, test } from "./guards";

for (const theme of ["dark", "light"] as const) {
  test(`Kitchen sink renders in the ${theme} theme`, async ({ page, request }) => {
    await putSettings(request, { ...DEFAULT_SETTINGS, theme });
    await open(page, "/kitchen-sink");
    await expect(page.getByRole("heading", { name: "Kitchen sink" })).toBeVisible();
    for (const name of ["Buttons", "Inputs", "Tabs", "Virtualised table", "Chart", "Field canvas and colour scales"]) {
      await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
    }
    await expect(page.getByRole("img", { name: "Test geometry in 3D" })).toBeVisible();
    await expect(page.getByRole("img", { name: /Test pattern: the shape of a 2D cylindrical wave/ }).first()).toBeVisible();
    await expect(page.getByRole("tree", { name: "Structure" })).toBeVisible();
  });
}
