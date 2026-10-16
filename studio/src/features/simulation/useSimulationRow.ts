import { useParams } from "react-router";
import type { SimulationRow } from "../../api/client";
import { useWorkspace } from "../../api/queries";

/** The workspace row of `/sim/:id/...`, with the workspace query's loading and error state. */
export function useSimulationRow(): {
  id: string | undefined;
  row: SimulationRow | undefined;
  workspace: ReturnType<typeof useWorkspace>;
} {
  const { id } = useParams();
  const workspace = useWorkspace();
  const row = workspace.data?.simulations.find((r) => r.id === id);
  return { id, row, workspace };
}
