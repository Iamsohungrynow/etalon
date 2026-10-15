import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "./styles/index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter } from "react-router";
import { createApi } from "./api/client";
import { adoptToken } from "./api/token";
import { App } from "./app/App";
import { routes } from "./app/routes";
import { createI18n, initialLanguage } from "./i18n";

// Before the router reads the URL: move ?token= into storage and out of the address bar.
const token = adoptToken();
const router = createBrowserRouter(routes);

const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root");
createRoot(root).render(
  <StrictMode>
    <App api={createApi(token)} i18n={createI18n(initialLanguage())} router={router} />
  </StrictMode>,
);
