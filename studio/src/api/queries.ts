/** Every server call goes through TanStack Query (CLAUDE.md, frontend conventions). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "./ApiProvider";
import { unwrap, type Settings } from "./client";

export const queryKeys = {
  workspace: ["workspace"],
  settings: ["settings"],
  system: ["system"],
} as const;

export function useWorkspace() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.workspace,
    queryFn: () => unwrap(api.GET("/api/workspace")),
    refetchOnWindowFocus: true,
  });
}

export function useSettings() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: () => unwrap(api.GET("/api/settings")),
    staleTime: Infinity,
  });
}

/** Versions and GPUs. The first answer can take seconds while the GPU probe runs. */
export function useSystem() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.system,
    queryFn: () => unwrap(api.GET("/api/system")),
    staleTime: Infinity,
  });
}

/**
 * Save the full settings. Shown at once (optimistic) and rolled back on error, except
 * a workspace change, which waits for the server to check the folder.
 */
export function useUpdateSettings() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (next: Settings) => unwrap(api.PUT("/api/settings", { body: next })),
    onMutate: async (next: Settings) => {
      await client.cancelQueries({ queryKey: queryKeys.settings });
      const previous = client.getQueryData<Settings>(queryKeys.settings);
      if (previous && next.workspace === previous.workspace) {
        client.setQueryData(queryKeys.settings, next);
      }
      return { previous };
    },
    onError: (_error, _next, result) => {
      if (result?.previous) client.setQueryData(queryKeys.settings, result.previous);
    },
    onSuccess: (saved, _next, result) => {
      client.setQueryData(queryKeys.settings, saved);
      if (saved.workspace !== result?.previous?.workspace) {
        void client.invalidateQueries({ queryKey: queryKeys.workspace });
      }
    },
  });
}
