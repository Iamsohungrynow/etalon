import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";
import type { SimulationRow } from "../../api/client";
import { cx } from "../../components/cx";
import { Value } from "../../components/Value";
import { StatusCell } from "../workspace/StatusCell";

interface SimulationHeaderProps {
  row: SimulationRow;
  /** Buttons on the right (Run, Open in editor, Cancel...). */
  actions?: ReactNode;
}

/**
 * The script's title with its path beside it, its status, the Setup · Run · Results
 * switch, and the screen's actions.
 */
export function SimulationHeader({ row, actions }: SimulationHeaderProps) {
  const { t } = useTranslation();
  const link = ({ isActive }: { isActive: boolean }) =>
    cx(
      "motion flex h-full items-center border-b-2 px-1 text-body transition-colors",
      isActive ? "border-accent text-text" : "border-transparent text-secondary hover:text-text",
    );
  return (
    <div className="flex h-11 shrink-0 items-stretch gap-6 border-b border-rule px-4">
      <div className="flex min-w-0 items-baseline gap-3 self-center">
        <h1 className="max-w-[28rem] shrink-0 truncate text-h3 font-semibold" title={row.title}>
          <Value mono={false}>{row.title}</Value>
        </h1>
        <Value className="truncate text-dense text-muted" title={row.path}>
          {row.path}
        </Value>
        <span className="text-dense">
          <StatusCell row={row} />
        </span>
      </div>
      <nav aria-label={t("simulation.views")} className="flex items-stretch gap-4">
        <NavLink to={`/sim/${row.id}/setup`} className={link}>
          {t("simulation.setup")}
        </NavLink>
        <NavLink to={`/sim/${row.id}/run`} className={link}>
          {t("simulation.run")}
        </NavLink>
        <NavLink to={`/sim/${row.id}/results`} className={link}>
          {t("simulation.results")}
        </NavLink>
      </nav>
      <div className="ml-auto flex items-center gap-2">{actions}</div>
    </div>
  );
}
