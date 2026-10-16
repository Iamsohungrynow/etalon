import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSpectra, type ResultMeta } from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { Button } from "../../components/Button";
import { Chart } from "../../components/Chart";
import { EmptyState } from "../../components/EmptyState";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Skeleton } from "../../components/Skeleton";
import { Value } from "../../components/Value";
import { saveBlob, toCsv } from "./download";

interface SpectraTabProps {
  meta: ResultMeta;
}

/** Point monitors: |F| and phase against wavelength, a data table, CSV export. */
export function SpectraTab({ meta }: SpectraTabProps) {
  const { t } = useTranslation();
  const points = meta.monitors.filter((m) => m.geometry === "point");
  const [monitorName, setMonitorName] = useState(points[0]?.name ?? "");
  const monitor = points.find((m) => m.name === monitorName) ?? points[0];
  const [view, setView] = useState<"chart" | "table">("chart");
  const spectra = useSpectra(meta.result_id, monitor?.name ?? null);

  const derived = useMemo(() => {
    if (!spectra.data) return null;
    const x = spectra.data.wavelengths_um;
    const entries = Object.entries(spectra.data.components);
    return {
      x,
      entries,
      magnitude: entries.map(([name, s], i) => ({
        name: t("results.spectra.magnitudeOf", { component: name }),
        x,
        y: s.re.map((re, k) => Math.hypot(re, s.im[k] ?? 0)),
        colorIndex: i,
      })),
      phase: entries.map(([name, s], i) => ({
        name: t("results.spectra.phaseOf", { component: name }),
        x,
        y: s.re.map((re, k) => Math.atan2(s.im[k] ?? 0, re)),
        colorIndex: i,
        dashed: true,
      })),
    };
  }, [spectra.data, t]);

  if (!monitor) {
    return <EmptyState title={t("results.spectra.none")}>{t("results.spectra.noneHint")}</EmptyState>;
  }

  const exportCsv = () => {
    if (!derived) return;
    const header = ["wavelength_um", ...derived.entries.flatMap(([c]) => [`${c}_re`, `${c}_im`])];
    const rows = derived.x.map((w, k) => [w, ...derived.entries.flatMap(([, s]) => [s.re[k] ?? NaN, s.im[k] ?? NaN])]);
    saveBlob(new Blob([toCsv(header, rows)], { type: "text/csv" }), `${meta.simulation_id}_${monitor.name}.csv`);
  };

  let body;
  if (spectra.isPending) {
    body = (
      <div role="status" className="flex items-center gap-2 px-4 py-6 text-dense text-secondary">
        <Skeleton width="8rem" /> {t("results.spectra.loading")}
      </div>
    );
  } else if (spectra.isError) {
    body = <LoadError error={spectra.error} onRetry={() => void spectra.refetch()} />;
  } else if (derived) {
    body = (
      <div className="grid min-h-0 flex-1 grid-rows-2 gap-0">
        <Chart
          label={t("results.spectra.magnitude")}
          series={derived.magnitude}
          xLabel={t("results.spectra.x")}
          yLabel={t("results.spectra.yMagnitude")}
          tableXHeader={t("results.spectra.x")}
          showTable={view === "table"}
          className="min-h-0"
        />
        <Chart
          label={t("results.spectra.phase")}
          series={derived.phase}
          xLabel={t("results.spectra.x")}
          yLabel={t("results.spectra.yPhase")}
          tableXHeader={t("results.spectra.x")}
          showTable={view === "table"}
          className="min-h-0 border-t border-rule-subtle"
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-4 border-b border-rule-subtle px-4 py-2">
        <span className="micro-label">{t("results.spectra.monitor")}</span>
        <Select
          label={t("results.spectra.monitor")}
          value={monitor.name}
          onValueChange={setMonitorName}
          options={points.map((m) => ({ value: m.name, label: <Value>{m.name}</Value> }))}
        />
        <Segmented
          label={t("results.spectra.view")}
          value={view}
          onValueChange={setView}
          options={[
            { value: "chart", label: t("results.spectra.chart") },
            { value: "table", label: t("results.spectra.table") },
          ]}
        />
        <span className="ml-auto" />
        <Button icon={<Download size={14} aria-hidden />} onClick={exportCsv} disabled={!derived}>
          {t("results.spectra.exportCsv")}
        </Button>
      </div>
      {body}
    </div>
  );
}
