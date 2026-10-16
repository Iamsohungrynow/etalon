import { useTranslation } from "react-i18next";
import type { ResultMeta } from "../../api/queries";
import { Value } from "../../components/Value";
import { formatCount, formatDuration } from "../../format/numbers";
import { formatFullDateTime } from "../../format/time";

interface ResultMetaBarProps {
  meta: ResultMeta;
}

/** Reproducibility on every result (spec §3.6): version, backend, device, grid, time, script sha. */
export function ResultMetaBar({ meta }: ResultMetaBarProps) {
  const { t, i18n } = useTranslation();
  const item = (label: string, value: string, title?: string) => (
    <span className="flex items-baseline gap-1.5">
      <span className="micro-label">{label}</span>
      <Value className="text-text" title={title}>
        {value}
      </Value>
    </span>
  );
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-rule bg-surface px-4 py-2 text-dense">
      {item(t("results.meta.finished"), formatFullDateTime(meta.finished_at, i18n.language))}
      {item(t("results.meta.version"), meta.etalon_version)}
      {item(t("results.meta.backend"), `${meta.backend} · ${meta.device}`)}
      {item(t("results.meta.precision"), meta.precision)}
      {item(t("results.meta.grid"), `${meta.grid.nx} × ${meta.grid.ny} · ${meta.grid.dx.toPrecision(3)} µm`)}
      {item(t("results.meta.steps"), formatCount(meta.steps, i18n.language))}
      {item(t("results.meta.wall"), formatDuration(meta.wall_time_s))}
      {item(t("results.meta.rate"), formatCount(meta.cells_per_s, i18n.language, 3))}
      {item(t("results.meta.script"), meta.script_sha256.slice(0, 7), meta.script_sha256)}
    </div>
  );
}
