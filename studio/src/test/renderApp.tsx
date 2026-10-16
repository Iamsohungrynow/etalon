import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { createMemoryRouter } from "react-router";
import { createApi } from "../api/client";
import { App } from "../app/App";
import { routes } from "../app/routes";
import { createI18n, type Language } from "../i18n";
import { fakeServer, type FakeServer } from "./fakeServer";

export const TEST_TOKEN = "test-token";

/** The whole app on a memory router, talking to a fake server. */
export function renderApp(path = "/", server: FakeServer = fakeServer(), language: Language = "en") {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const i18n = createI18n(language);
  const api = createApi(TEST_TOKEN, server.fetch);
  const utils = render(<App api={api} token={TEST_TOKEN} i18n={i18n} router={router} />);
  return { ...utils, router, server, i18n };
}

/** A component with i18n only (design-system components need no server). */
export function renderWithI18n(ui: ReactNode, language: Language = "en") {
  const i18n = createI18n(language);
  return { ...render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>), i18n };
}
