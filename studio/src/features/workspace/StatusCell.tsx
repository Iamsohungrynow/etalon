import {
  Ban,
  Circle,
  CircleDashed,
  CircleQuestionMark,
  CircleX,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { SimulationRow, SimulationStatus } from "../../api/client";
import { cx } from "../../components/cx";

const ICONS: Record<SimulationStatus, LucideIcon> = {
  done: Circle,
  running: CircleDashed,
  draft: Circle,
  failed: CircleX,
  cancelled: Ban,
  unknown: CircleQuestionMark,
};

const TONES: Record<SimulationStatus, string> = {
  done: "text-ok",
  running: "text-accent-ink",
  draft: "text-muted",
  failed: "text-error",
  cancelled: "text-secondary",
  unknown: "text-warn",
};

interface StatusCellProps {
  row: Pick<SimulationRow, "status" | "status_reason" | "stale">;
}

/** Glyph + word (+ "stale"), so the status never relies on colour alone (spec §7). */
export function StatusCell({ row }: StatusCellProps) {
  const { t } = useTranslation();
  const Icon = ICONS[row.status];
  const reason = row.status_reason ? t(`status.reason.${row.status_reason}`) : undefined;
  return (
    <span className="inline-flex items-center gap-1.5" title={reason}>
      <Icon
        size={12}
        aria-hidden
        className={cx("shrink-0", TONES[row.status])}
        fill={row.status === "done" ? "currentColor" : "none"}
      />
      <span>{t(`status.${row.status}`)}</span>
      {row.stale ? (
        <span title={t("workspace.staleHint")} className="micro-label border border-warn px-1 text-warn">
          {t("workspace.stale")}
        </span>
      ) : null}
    </span>
  );
}
