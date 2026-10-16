// Setup: loading, script errors, the tree ↔ inspector selection, estimate and warnings.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SimulationSpec } from "../../api/queries";
import { binaryFrame } from "../../test/binaryFrame";
import { FOLDER, fakeServer, json, makeRow } from "../../test/fakeServer";
import { renderApp } from "../../test/renderApp";
import { TEST_PREVIEW } from "../kitchen/samples";

vi.mock("../../components/Viewport3D", async () => ({ Viewport3D: (await import("../../test/heavyStubs")).Viewport3DStub }));
vi.mock("../../components/FieldCanvas", async () => ({ FieldCanvas: (await import("../../test/heavyStubs")).FieldCanvasStub }));

const ROW = makeRow({ id: "abc123def456", path: "strip.py" });

const SPEC: SimulationSpec = {
  script_sha256: "f".repeat(64),
  spec: {},
  preview: TEST_PREVIEW,
  estimate: { cells: 19136, memory_bytes: 4_200_000, steps: 2600, dt_s: 1.16e-16, run_time_s: 3e-13, seconds: 4.2, cells_per_s: 1.2e7, basis: "measured" },
  warnings: [
    { code: "mesh_coarse", severity: "warning", object_id: "medium:0", params: { cells_per_wavelength: 14.2, minimum: 20, medium: "Si", wavelength_um: 1.45 } },
  ],
  stdout_tail: "",
};

function server(spec: () => Response) {
  return fakeServer(
    { workspace: { folder: FOLDER, simulations: [ROW], truncated: false } },
    {
      "GET /api/simulations/abc123def456/spec": spec,
      "GET /api/simulations/abc123def456/permittivity": () =>
        new Response(
          binaryFrame({ kind: "permittivity", shape: [2, 2], extent: [-1, 1, -1, 1], min: 2.08, max: 12.08, component: "Ex", unit: "", pml_cells: 12 }, [2.08, 12.08, 12.08, 2.08]),
          { headers: { "Content-Type": "application/octet-stream" } },
        ),
      "POST /api/simulations/abc123def456/run": () => json({ job_id: "job-1", result_id: "abc123def456~1" }, 202),
    },
  );
}

describe("Setup", () => {
  it("says it is building, then shows the tree, the 3D view, the estimate and warnings", async () => {
    let release: (r: Response) => void = () => {};
    renderApp("/sim/abc123def456/setup", server(() => new Promise<Response>((r) => (release = r)) as unknown as Response));
    expect(await screen.findByText("Building simulation…")).toBeVisible();
    release(json(SPEC));
    expect(await screen.findByRole("tree", { name: "Structure" })).toBeVisible();
    expect(screen.getByRole("img", { name: "The simulation in 3D" })).toBeVisible();
    expect(screen.getByText("Estimate")).toBeVisible();
    expect(screen.getByText("~4s")).toBeVisible();
    const warnings = screen.getByRole("list", { name: "Warnings" });
    expect(warnings).toHaveTextContent("14.2 cells per wavelength in Si at 1.45 µm; at least 20 are needed.");
    expect(screen.getByRole("button", { name: "Run" })).toBeEnabled();
  });

  it("fills the inspector from the tree and from a warning's Show", async () => {
    renderApp("/sim/abc123def456/setup", server(() => json(SPEC)));
    const tree = await screen.findByRole("tree", { name: "Structure" });
    await userEvent.click(within(tree).getByText("dipole"));
    expect(await screen.findByText("1.55 µm")).toBeVisible();
    const inspector = screen.getByRole("heading", { name: "Inspector" }).closest("aside") as HTMLElement;
    expect(within(inspector).getByText("Hz")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(await screen.findByText("Refractive index")).toBeVisible();
    expect(screen.getByText("3.4760")).toBeVisible();
  });

  it("shows the solver's permittivity in the slice view, with a readout", async () => {
    renderApp("/sim/abc123def456/setup", server(() => json(SPEC)));
    await userEvent.click(await screen.findByRole("radio", { name: "Slice" }));
    const slice = await screen.findByRole("img", { name: /Relative permittivity on the simulated plane/ });
    await userEvent.hover(slice);
    expect(await screen.findByText(/εr 12.08/)).toBeVisible();
  });

  it("shows a script error with its line and traceback, and disables Run", async () => {
    const error = { code: "script_error", message: "KeyError: 'rnig'", traceback: 'File "strip.py", line 12, in <module>\nKeyError: \'rnig\'', line: 12, stdout_tail: "" };
    renderApp("/sim/abc123def456/setup", server(() => json(error, 422)));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The script failed");
    expect(alert).toHaveTextContent("at line 12");
    expect(within(alert).getByText(/line 12, in <module>/)).toHaveClass("text-error");
    await waitFor(() => expect(screen.getByRole("button", { name: "Run" })).toBeDisabled());
  });

  it("says when a script defines no simulation", async () => {
    renderApp("/sim/abc123def456/setup", server(() => json({ code: "no_simulation", message: "", traceback: "", line: null, stdout_tail: "" }, 422)));
    expect(await screen.findByText("This script defines no etalon Simulation")).toBeVisible();
  });

  it("starts a run and moves to the Run screen", async () => {
    const s = server(() => json(SPEC));
    const { router } = renderApp("/sim/abc123def456/setup", s);
    await screen.findByRole("tree", { name: "Structure" }); // Run is disabled until the spec is in
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    // The Run route loads lazily; the router moves once its module is in.
    await waitFor(() => expect(router.state.location.pathname).toBe("/sim/abc123def456/run"), {
      timeout: 15_000,
    });
    expect(s.calls.some((c) => c.method === "POST" && c.path.endsWith("/run"))).toBe(true);
  });
});
