// V6: the token's journey, the header, and how failures map to errors.
import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { json, fakeServer } from "../test/fakeServer";
import { renderApp, TEST_TOKEN } from "../test/renderApp";
import { createApi, NetworkError, ServerError, SessionEndedError, unwrap } from "./client";
import { adoptToken, TOKEN_STORAGE_KEY } from "./token";

describe("V6: token", () => {
  it("moves from the URL into storage and leaves the address bar", () => {
    window.history.replaceState(null, "", "/settings?token=abc123&x=1#here");
    expect(adoptToken()).toBe("abc123");
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe("abc123");
    expect(window.location.pathname + window.location.search + window.location.hash).toBe(
      "/settings?x=1#here",
    );
    expect(adoptToken()).toBe("abc123");
  });

  it("comes back from storage on a later visit", () => {
    window.history.replaceState(null, "", "/");
    localStorage.setItem(TOKEN_STORAGE_KEY, "saved");
    expect(adoptToken()).toBe("saved");
  });

  it("survives blocked storage for this tab", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    window.history.replaceState(null, "", "/?token=tab-only");
    expect(adoptToken()).toBe("tab-only");
    window.history.replaceState(null, "", "/");
    expect(adoptToken()).toBe("tab-only");
    setItem.mockRestore();
    getItem.mockRestore();
  });

  it("is absent when nothing gave one", () => {
    window.history.replaceState(null, "", "/");
    expect(adoptToken()).toBeNull();
  });
});

describe("V6: client", () => {
  it("sends the token header on every request", async () => {
    const server = fakeServer();
    await unwrap(createApi("secret", server.fetch).GET("/api/settings"));
    expect(server.calls).toEqual([
      expect.objectContaining({ method: "GET", path: "/api/settings", token: "secret" }),
    ]);
  });

  it("maps 401, error bodies, 422 and an unreachable server", async () => {
    const server = fakeServer(
      {},
      {
        "GET /api/settings": () => json({ code: "unauthorized", message: "no" }, 401),
        "GET /api/workspace": () => json({ code: "workspace_missing", message: "gone" }, 404),
        "PUT /api/settings": () =>
          json({ detail: [{ type: "workspace_not_found", loc: ["body", "workspace"], msg: "x" }] }, 422),
      },
    );
    const api = createApi("t", server.fetch);
    await expect(unwrap(api.GET("/api/settings"))).rejects.toBeInstanceOf(SessionEndedError);
    const missing = await unwrap(api.GET("/api/workspace")).catch((e: unknown) => e);
    expect(missing).toBeInstanceOf(ServerError);
    expect((missing as ServerError).code).toBe("workspace_missing");
    const invalid = await unwrap(api.PUT("/api/settings", { body: server.state.settings })).catch(
      (e: unknown) => e,
    );
    expect((invalid as ServerError).issues[0]?.type).toBe("workspace_not_found");
    const down = createApi("t", () => Promise.reject(new TypeError("Failed to fetch")));
    await expect(unwrap(down.GET("/api/system"))).rejects.toBeInstanceOf(NetworkError);
  });

  it("ends the session on the first 401", async () => {
    const server = fakeServer({}, { "GET /api/workspace": () => json({ code: "unauthorized" }, 401) });
    renderApp("/", server);
    expect(await screen.findByRole("heading", { name: "This Studio session has ended" })).toBeVisible();
    expect(screen.getByText("etalon studio")).toHaveAttribute("translate", "no");
    await waitFor(() => expect(document.title).toBe("This Studio session has ended · etalon Studio"));
    expect(server.calls.every((call) => call.token === TEST_TOKEN)).toBe(true);
  });
});
