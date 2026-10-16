import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { JobProgress } from "../../api/jobSocket";
import { Chart } from "../../components/Chart";
import { Segmented } from "../../components/Segmented";

interface EnergyChartProps {
  progress: readonly JobProgress[];
}

/** Field energy against step, relative to its peak, on a log axis (spec §5.3). */
export function EnergyChart({ progress }: EnergyChartProps) {
  const { t } = useTranslation();
  const [view, setView] = useState<"chart" | "table">("chart");
  const series = useMemo(() => {
    const peak = progress.reduce((m, p) => Math.max(m, p.energy), 0);
    const points = peak > 0 ? progress.filter((p) => p.energy > 0) : [];
    return [
      {
        name: t("run.energy.series"),
        x: points.map((p) => p.step),
        y: points.map((p) => p.energy / peak),
      },
    ];
  }, [progress, t]);
  return (
    <section aria-labelledby="energy-title" className="flex min-h-0 flex-col">
      <div className="flex items-center gap-3 px-3 py-1.5">
        <h2 id="energy-title" className="micro-label">
          {t("run.energy.title")}
        </h2>
        <span className="ml-auto" />
        <Segmented
          label={t("run.energy.view")}
          value={view}
          onValueChange={setView}
          options={[
            { value: "chart", label: t("run.energy.chart") },
            { value: "table", label: t("run.energy.table") },
          ]}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <Chart
          label={t("run.energy.label")}
          series={series}
          xLabel={t("run.energy.x")}
          yLabel={t("run.energy.y")}
          yScale="log"
          tableXHeader={t("run.energy.x")}
          showTable={view === "table"}
          legend={false}
          className="h-full"
        />
      </div>
    </section>
  );
}
