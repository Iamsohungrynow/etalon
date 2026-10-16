import { QueryClientProvider } from "@tanstack/react-query";
import type { i18n } from "i18next";
import { useState } from "react";
import { I18nextProvider } from "react-i18next";
import { RouterProvider, type createBrowserRouter } from "react-router";
import { ApiProvider } from "../api/ApiProvider";
import type { Api } from "../api/client";
import { createQueryClient } from "./queryClient";
import { SessionEndedScreen } from "./SessionEndedScreen";

export type StudioRouter = ReturnType<typeof createBrowserRouter>;

interface AppProps {
  api: Api;
  token: string | null;
  i18n: i18n;
  router: StudioRouter;
}

export function App({ api, token, i18n, router }: AppProps) {
  const [ended, setEnded] = useState(false);
  const [queryClient] = useState(() => createQueryClient(() => setEnded(true)));
  return (
    <I18nextProvider i18n={i18n}>
      <ApiProvider api={api} token={token}>
        <QueryClientProvider client={queryClient}>
          {ended ? <SessionEndedScreen /> : <RouterProvider router={router} />}
        </QueryClientProvider>
      </ApiProvider>
    </I18nextProvider>
  );
}
