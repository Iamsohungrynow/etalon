import { createContext, useContext, type ReactNode } from "react";
import type { Api } from "./client";

const ApiContext = createContext<Api | null>(null);

interface ApiProviderProps {
  api: Api;
  children: ReactNode;
}

export function ApiProvider({ api, children }: ApiProviderProps) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi() outside <ApiProvider>");
  return api;
}
