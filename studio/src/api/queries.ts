/** Every server call goes through TanStack Query (CLAUDE.md, frontend conventions). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { decodeArray } from "../field/binary";
import { useApi } from "./ApiProvider";
import { unwrap, unwrapNoContent, type Settings } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];
export type SimulationSpec = Schemas["SimulationSpec"];
export type Preview = Schemas["Preview"];
export type SetupWarning = Schemas["Warning"];
export type ScriptError = Schemas["ScriptError"];
export type ResultMeta = Schemas["ResultMeta"];
export type TemplateId = Schemas["Template"]["id"];
export type FieldQuantity = Schemas["FieldHeader"]["quantity"];
export type PermittivityArray = { header: Schemas["PermittivityHeader"]; data: Float32Array };
export type FieldArray = { header: Schemas["FieldHeader"]; data: Float32Array };

/**
 * openapi-fetch types every response as `Readable<T>`, which widens tuples such as
 * `region_cells: [rx, ry]` to plain arrays. The JSON is exactly the schema, so the
 * generated component types are restored here, once, at the boundary.
 */
function asSchema<T>(data: unknown): T {
  return data as T;
}

export const queryKeys = {
  workspace: ["workspace"],
  settings: ["settings"],
  system: ["system"],
  templates: ["templates"],
  spec: (id: string) => ["spec", id] as const,
  permittivity: (id: string, sha: string, component: string) =>
    ["permittivity", id, sha, component] as const,
  result: (id: string) => ["result", id] as const,
  field: (id: string, monitor: string, component: string, quantity: string, wavelength: number) =>
    ["field", id, monitor, component, quantity, wavelength] as const,
  spectra: (id: string, monitor: string) => ["spectra", id, monitor] as const,
} as const;

export function useWorkspace() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.workspace,
    queryFn: () => unwrap(api.GET("/api/workspace")),
    refetchOnWindowFocus: true,
    // While a run is going, its row's step count and ETA come from the runner's status.json.
    refetchInterval: (query) =>
      query.state.data?.simulations.some((row) => row.status === "running") ? 1000 : false,
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

export function useTemplates() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.templates,
    queryFn: () => unwrap(api.GET("/api/templates")),
    staleTime: Infinity,
  });
}

export function useCreateSimulation() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { template: TemplateId; name: string }) =>
      unwrap(api.POST("/api/simulations", { body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.workspace }),
  });
}

/**
 * The script's simulation, as the solver will see it. The server caches by the script's
 * sha256, so refetching on focus (after an edit in the user's editor) is cheap.
 */
export function useSpec(id: string | undefined) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.spec(id ?? ""),
    queryFn: async () =>
      asSchema<SimulationSpec>(
        await unwrap(api.GET("/api/simulations/{id}/spec", { params: { path: { id: id ?? "" } } })),
      ),
    enabled: Boolean(id),
    refetchOnWindowFocus: true,
    retry: false,
  });
}

/** The solver's own εr on the Ex or Ey nodes, as float32 (plan-u1 §13.1). */
export function usePermittivity(id: string | undefined, sha: string | undefined, component = "Ex") {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.permittivity(id ?? "", sha ?? "", component),
    queryFn: async (): Promise<PermittivityArray> => {
      const buffer = await unwrap(
        api.GET("/api/simulations/{id}/permittivity", {
          params: { path: { id: id ?? "" }, query: { component: component as "Ex" | "Ey" } },
          parseAs: "arrayBuffer",
        }),
      );
      return decodeArray<PermittivityArray["header"]>(buffer);
    },
    enabled: Boolean(id && sha),
    staleTime: Infinity,
  });
}

export function useOpenInEditor() {
  const api = useApi();
  return useMutation({
    mutationFn: (id: string) =>
      unwrapNoContent(api.POST("/api/simulations/{id}/open", { params: { path: { id } } })),
  });
}

export function useCalibrate() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/calibrate")),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["spec"] }),
  });
}

export function useRunSimulation() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.POST("/api/simulations/{id}/run", { params: { path: { id } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.workspace }),
  });
}

export function useCancelJob() {
  const api = useApi();
  return useMutation({
    mutationFn: (jobId: string) =>
      unwrap(api.DELETE("/api/jobs/{job_id}", { params: { path: { job_id: jobId } } })),
  });
}

export function useResult(id: string | null | undefined) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.result(id ?? ""),
    queryFn: async () =>
      asSchema<ResultMeta>(
        await unwrap(api.GET("/api/results/{id}", { params: { path: { id: id ?? "" } } })),
      ),
    enabled: Boolean(id),
  });
}

/** One plane-monitor slice as float32 (plan-u1 §13.1, §13.4). */
export function useFieldSlice(
  id: string | null | undefined,
  monitor: string | null,
  component: string | null,
  quantity: FieldQuantity,
  wavelengthIndex: number,
) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.field(id ?? "", monitor ?? "", component ?? "", quantity, wavelengthIndex),
    queryFn: async (): Promise<FieldArray> => {
      const buffer = await unwrap(
        api.GET("/api/results/{id}/fields/{monitor}", {
          params: {
            path: { id: id ?? "", monitor: monitor ?? "" },
            query: { component: component ?? "", quantity, wavelength_index: wavelengthIndex },
          },
          parseAs: "arrayBuffer",
        }),
      );
      return decodeArray<FieldArray["header"]>(buffer);
    },
    enabled: Boolean(id && monitor && component),
    staleTime: Infinity,
    placeholderData: (previous) => previous, // keep the old image while the next loads
  });
}

export function useSpectra(id: string | null | undefined, monitor: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.spectra(id ?? "", monitor ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/results/{id}/spectra/{monitor}", {
          params: { path: { id: id ?? "", monitor: monitor ?? "" } },
        }),
      ),
    enabled: Boolean(id && monitor),
    staleTime: Infinity,
  });
}
