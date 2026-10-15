import type { SimulationRow } from "../../api/client";

/** Spec §5.1: draft → Setup, running → Run, finished → Results. */
export function rowTarget(row: Pick<SimulationRow, "id" | "status">): string {
  switch (row.status) {
    case "running":
      return `/sim/${row.id}/run`;
    case "done":
    case "failed":
    case "cancelled":
      return `/sim/${row.id}/results`;
    case "draft":
    case "unknown":
      return `/sim/${row.id}/setup`;
  }
}
