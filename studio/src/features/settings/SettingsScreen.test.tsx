// V8: Settings loads, saves each control, rolls back on failure, applies theme and language.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { NO_GPU, fakeServer, json } from "../../test/fakeServer";
import { renderApp } from "../../test/renderApp";

const puts = (server: ReturnType<typeof fakeServer>) =>
  server.calls.filter((c) => c.method === "PUT").map((c) => c.body);

describe("V8: Settings", () => {
  it("shows a loading state, then every section", async () => {
    renderApp("/settings");
    expect(screen.getByText("Loading settings…")).toBeVisible();
    for (const name of ["Backend", "Workspace folder", "Language", "Theme", "Length units", "Live field snapshots", "Privacy", "About"]) {
      expect(await screen.findByRole("heading", { name })).toBeInTheDocument();
    }
    expect(screen.getByText(/Studio makes no network requests/)).toBeVisible();
    expect(await screen.findByText("cuda:0 · NVIDIA GeForce RTX 4060 Ti")).toBeVisible();
    expect(screen.getByText("8.585 GB")).toBeVisible();
  });

  it("shows a load failure with Retry", async () => {
    renderApp("/settings", fakeServer({}, { "GET /api/settings": () => json({ code: "x", message: "y" }, 500) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This could not be loaded.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
  });

  it("saves theme, units and snapshots with the full settings, and applies the theme", async () => {
    const server = fakeServer();
    renderApp("/settings", server);
    await userEvent.click(await screen.findByRole("radio", { name: "Light" }));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    await userEvent.click(screen.getByRole("radio", { name: "nm" }));
    await userEvent.click(screen.getByRole("switch", { name: "Live field snapshots" }));
    await waitFor(() => expect(puts(server)).toHaveLength(3));
    expect(puts(server)).toEqual([
      expect.objectContaining({ theme: "light", units: "um", live_snapshots: false }),
      expect.objectContaining({ theme: "light", units: "nm", live_snapshots: false }),
      expect.objectContaining({ theme: "light", units: "nm", live_snapshots: true, workspace: server.state.settings.workspace }),
    ]);
  });

  it("switches every string to Chinese and back", async () => {
    renderApp("/settings");
    await userEvent.click(await screen.findByRole("radio", { name: "简体中文" }));
    expect(await screen.findByRole("heading", { name: "设置" })).toBeVisible();
    await waitFor(() => expect(document.documentElement.lang).toBe("zh-CN"));
    expect(screen.getByRole("link", { name: "工作区" })).toBeVisible();
    await userEvent.click(screen.getByRole("radio", { name: "English" }));
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeVisible();
  });

  it("rolls a failed save back and says so next to the control", async () => {
    const server = fakeServer({}, { "PUT /api/settings": () => json({ code: "x", message: "y" }, 500) });
    renderApp("/settings", server);
    const light = await screen.findByRole("radio", { name: "Light" });
    await userEvent.click(light);
    const theme = screen.getByRole("heading", { name: "Theme" }).closest("section") as HTMLElement;
    expect(await within(theme).findByRole("alert")).toHaveTextContent("The change was not saved.");
    expect(within(theme).getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  });

  it("picks a backend from the detected devices", async () => {
    const server = fakeServer();
    renderApp("/settings", server);
    await userEvent.click(await screen.findByRole("combobox", { name: "Backend" }));
    await userEvent.click(await screen.findByRole("option", { name: "cuda:0 · NVIDIA GeForce RTX 4060 Ti · 8.585 GB" }));
    await waitFor(() => expect(puts(server)).toEqual([expect.objectContaining({ backend: "cuda:0" })]));
  });

  it("explains a machine without CuPy", async () => {
    renderApp("/settings", fakeServer({ system: NO_GPU }));
    expect(await screen.findByText(/CuPy is not installed/)).toBeVisible();
    expect(screen.getByText("etalon[gpu]")).toHaveAttribute("translate", "no");
  });

  it("switches the workspace folder, and shows the server's reason when it refuses", async () => {
    const server = fakeServer({}, {
      "PUT /api/settings": async (request) => {
        const body = (await request.json()) as { workspace: string };
        if (body.workspace.endsWith("missing")) {
          return json({ detail: [{ type: "workspace_not_found", loc: ["body", "workspace"], msg: "x", input: body.workspace }] }, 422);
        }
        server.state.settings = { ...server.state.settings, workspace: body.workspace };
        return json(server.state.settings);
      },
    });
    renderApp("/settings", server);
    const field = await screen.findByRole("textbox", { name: "Folder path" });
    const apply = screen.getByRole("button", { name: "Apply" });
    expect(apply).toBeDisabled();
    await userEvent.clear(field);
    await userEvent.type(field, "D:\\missing");
    await userEvent.click(apply);
    expect(await screen.findByText("This folder does not exist.")).toBeVisible();
    expect(field).toHaveAttribute("aria-invalid", "true");
    await userEvent.clear(field);
    await userEvent.type(field, "D:\\designs");
    expect(field).not.toHaveAttribute("aria-invalid");
    await userEvent.click(apply);
    await waitFor(() => expect(server.state.settings.workspace).toBe("D:\\designs"));
    await waitFor(() => expect(server.calls.filter((c) => c.path === "/api/workspace").length).toBeGreaterThan(1));
  });
});
