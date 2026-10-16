import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { SimulationRow } from "../../api/client";
import { Table, type Column } from "../../components/Table";
import { Value } from "../../components/Value";
import { formatCount, formatDuration, formatEta } from "../../format/numbers";
import { formatFullDateTime, formatLastRun } from "../../format/time";
import { rowTarget } from "./rowTarget";
import { StatusCell } from "./StatusCell";

interface WorkspaceTableProps {
  rows: readonly SimulationRow[];
  /** "Now" for "today"/"yesterday"; a prop so tests are deterministic. */
  now?: Date;
}

const EMPTY = "—";

export function WorkspaceTable({ rows, now }: WorkspaceTableProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const columns = useMemo<Column<SimulationRow>[]>(() => {
    const today = now ?? new Date();
    return [
      {
        id: "name",
        header: t("workspace.columns.name"),
        width: "minmax(12rem, 3fr)",
        cell: (row) => (
          // The script's title leads; its path stays visible under it, because the
          // script, not Studio, is the source of truth.
          <span className="block min-w-0 leading-tight">
            <Link
              to={rowTarget(row)}
              translate="no"
              title={row.path}
              className="stretched-link block truncate text-text focus-visible:outline-none"
            >
              {row.title}
            </Link>
            <span translate="no" className="block truncate font-mono text-dense text-muted">
              {row.path}
            </span>
          </span>
        ),
      },
      {
        id: "status",
        header: t("workspace.columns.status"),
        width: "minmax(7rem, 1fr)",
        cell: (row) => <StatusCell row={row} />,
      },
      {
        id: "lastRun",
        header: t("workspace.columns.lastRun"),
        width: "minmax(9rem, 1.4fr)",
        cell: (row) => {
          if (row.status === "running" && row.step != null && row.total_steps != null) {
            return (
              <>
                {t("workspace.step")}{" "}
                <Value>
                  {formatCount(row.step, locale)} / {formatCount(row.total_steps, locale)}
                </Value>
              </>
            );
          }
          if (!row.last_run) return <span className="text-muted">{EMPTY}</span>;
          return (
            <span className="tabular-nums" title={formatFullDateTime(row.last_run, locale)}>
              {formatLastRun(row.last_run, today, locale, t)}
            </span>
          );
        },
      },
      {
        id: "backend",
        header: t("workspace.columns.backend"),
        width: "6rem",
        cell: (row) => (
          <Value className={row.backend ? "" : "text-muted"} title={row.device ?? undefined}>
            {row.backend ?? EMPTY}
          </Value>
        ),
      },
      {
        id: "cells",
        header: t("workspace.columns.cells"),
        width: "5.5rem",
        align: "end",
        cell: (row) => (
          <Value className={row.cells == null ? "text-muted" : ""} title={row.cells?.toString()}>
            {row.cells == null ? EMPTY : formatCount(row.cells, locale)}
          </Value>
        ),
      },
      {
        id: "time",
        header: t("workspace.columns.time"),
        width: "5rem",
        align: "end",
        cell: (row) => {
          if (row.status === "running" && row.eta_s != null) return <Value>{formatEta(row.eta_s)}</Value>;
          if (row.wall_time_s != null) return <Value>{formatDuration(row.wall_time_s)}</Value>;
          return <span className="text-muted">{EMPTY}</span>;
        },
      },
    ];
  }, [t, locale, now]);
  return (
    <Table
      label={t("workspace.tableLabel")}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      rowHeight={44}
    />
  );
}
