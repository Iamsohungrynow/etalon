// Results: no run yet, metadata and stale banner, fields, spectra table, S-parameters disabled.
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ResultMeta } from "../../api/queries";
import { binaryFrame } from "../../test/binaryFrame";
import { FOLDER, fakeServer, json, makeRow } from "../../test/fakeServer";
import { renderApp } from "../../test/renderApp";
import { TEST_PREVIEW } from "../kitchen/samples";

vi.mock("../../components/FieldCanvas", async () => ({ FieldCanvas: (await import("../../test/heavyStubs")).FieldCanvasStub }));
vi.mock("../../components/Chart", async () => ({ Chart: (await import("../../test/heavyStubs")).ChartStub }));

const ID = "abc123def456";
const RESULT = `${ID}~20261016T093841Z`;

const META: ResultMeta = {
  result_id: RESULT,
  simulation_id: ID,
  title: "Photonic-crystal waveguide",
  status: "done",
  started_at: "2026-10-16T09:38:41Z",
  finished_at: "2026-10-16T09:39:06Z",
  etalon_version: "0.0.1",
  backend: "cpu",
  device: "AMD Ryzen 5 5600 6-Core Processor",
  precision: "single",
  grid: { nx: 184, ny: 104, dx: 0.02, dy: 0.02 },
  steps: 5354,
  dt_s: 4.67e-17,
  wall_time_s: 15.1,
  cells_per_s: 1.67e7,
  script_sha256: "e584ff48090fdc90444d49be96b116114dff570a5e1cc50de71e86311d4359a5",
  stale: true,
  preview: TEST_PREVIEW,
  monitors: [
    { name: "field", geometry: "plane", components: ["Ex", "Ey", "Hz"], wavelengths_um: [1.5, 1.55, 1.6], shape: [2, 2], extent: [-1, 1, -1, 1] },
    { name: "out", geometry: "point", components: ["Hz"], wavelengths_um: [1.5, 1.55, 1.6], shape: null, extent: null },
  ],
};

function server(row = makeRow({ id: ID, path: "phc.py", status: "done", last_result_id: RESULT })) {
  return fakeServer(
    { workspace: { folder: FOLDER, simulations: [row], truncated: false } },
    {
      [`GET /api/results/${encodeURIComponent(RESULT)}`]: () => json(META),
      [`GET /api/results/${RESULT}`]: () => json(META),
      [`GET /api/results/${RESULT}/fields/field`]: () =>
        new Response(binaryFrame({ kind: "field", shape: [2, 2], extent: [-1, 1, -1, 1], min: 0, max: 3, component: "Hz", unit: "A·s/m", quantity: "abs", wavelength_um: 1.55 }, [0, 1, 2, 3])),
      [`GET /api/results/${RESULT}/spectra/out`]: () =>
        json({ monitor: "out", wavelengths_um: [1.5, 1.55, 1.6], components: { Hz: { re: [1, 0, -1], im: [0, 1, 0] } } }),
    },
  );
}

describe("Results", () => {
  it("explains that there is nothing yet, with a way to run", async () => {
    renderApp(`/sim/${ID}/results`, server(makeRow({ id: ID, path: "phc.py" })));
    expect(await screen.findByRole("heading", { name: "No results yet" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Run again" })).toHaveAttribute("href", `/sim/${ID}/run`);
  });

  it("shows the run's metadata, the stale banner and the field", async () => {
    renderApp(`/sim/${ID}/results`, server());
    expect(await screen.findByText("AMD Ryzen 5 5600 6-Core Processor", { exact: false })).toBeVisible();
    expect(screen.getByText("e584ff4")).toHaveAttribute("title", META.script_sha256);
    expect(screen.getByText("These results are from an earlier version of this script.")).toBeVisible();
    expect(await screen.findByRole("img", { name: "Hz on monitor field" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "S-parameters" })).toBeDisabled();
  });

  it("lists point spectra as a table", async () => {
    renderApp(`/sim/${ID}/results`, server());
    await userEvent.click(await screen.findByRole("tab", { name: "Spectra" }));
    await userEvent.click(await screen.findByRole("radio", { name: "Table" }));
    const magnitude = await screen.findByRole("table", { name: "Spectrum magnitude" });
    expect(within(magnitude).getByText("|Hz|")).toBeVisible();
    expect(screen.getByRole("table", { name: "Spectrum phase" })).toHaveTextContent("phase of Hz");
  });
});
