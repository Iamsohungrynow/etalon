import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { NetworkError, SessionEndedError } from "../api/client";

/**
 * One QueryClient per app. A 401 anywhere ends the session (the whole page switches
 * to the session-ended screen); only an unreachable server is retried, once.
 */
export function createQueryClient(onSessionEnded: () => void): QueryClient {
  const onError = (error: unknown) => {
    if (error instanceof SessionEndedError) onSessionEnded();
  };
  return new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        retry: (failures, error) => error instanceof NetworkError && failures < 1,
        retryDelay: 500,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
