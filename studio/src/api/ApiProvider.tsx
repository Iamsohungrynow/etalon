import { createContext, useContext, type ReactNode } from "react";
import type { Api } from "./client";

interface ApiContextValue {
  api: Api;
  /** The Studio token; WebSockets carry it as a subprotocol (browsers cannot set headers). */
  token: string | null;
}

const ApiContext = createContext<ApiContextValue | null>(null);

interface ApiProviderProps {
  api: Api;
  token: string | null;
  children: ReactNode;
}

export function ApiProvider({ api, token, children }: ApiProviderProps) {
  return <ApiContext.Provider value={{ api, token }}>{children}</ApiContext.Provider>;
}

function useApiContext(): ApiContextValue {
  const value = useContext(ApiContext);
  if (!value) throw new Error("useApi() outside <ApiProvider>");
  return value;
}

export function useApi(): Api {
  return useApiContext().api;
}

export function useApiToken(): string | null {
  return useApiContext().token;
}
