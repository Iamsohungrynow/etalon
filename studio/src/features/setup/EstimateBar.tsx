import { CircleAlert, Gauge, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { SimulationSpec } from "../../api/queries";
import { useCalibrate, useSystem } from "../../api/queries";
import { Button } from "../../components/Button";
import { cx } from "../../components/cx";
import { Value } from "../../components/Value";
import { formatBytes, formatCount, formatDuration } from "../../format/numbers";
import { formatQuantity } from "../../format/units";
import { WarningText } from "./WarningText";

interface EstimateBarProps {
  spec: SimulationSpec;
  objectName: (id: string | null) => string | undefined;
  onSelect: (id: string) => void;
}

/** Always visible under Setup (spec §5.2): what the run will cost, and what looks wrong. */
export function EstimateBar({ spec, objectName, onSelect }: EstimateBarProps) {
  const { t, i18n } = useTranslation();
  const system = useSystem();
  const calibrate = useCalibrate();
  const estimate = spec.estimate;
  const device = system.data?.devices[0]?.name;
  const timeStep = estimate ? formatQuantity(estimate.dt_s, "time", "fs", i18n.language) : "";
  const item = (label: string, value: string) => (
    <span className="flex items-baseline gap-1.5">
      <span className="micro-label">{label}</span>
      <Value className="text-text">{value}</Value>
    </span>
  );
  return (
    <div className="shrink-0 border-t border-rule bg-surface">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2 text-dense">
        <span className="flex items-center gap-1.5 text-secondary">
          <Gauge size={14} aria-hidden />
          <span className="micro-label">{t("setup.estimate.label")}</span>
        </span>
        {estimate ? (
          <>
            {item(t("setup.estimate.cells"), formatCount(estimate.cells, i18n.language))}
            {item(t("setup.estimate.memory"), formatBytes(estimate.memory_bytes, i18n.language))}
            {item(t("setup.estimate.steps"), formatCount(estimate.steps, i18n.language))}
            {item(t("setup.estimate.dt"), timeStep)}
            <span className="flex items-baseline gap-1.5">
              <span className="micro-label">{t("setup.estimate.time")}</span>
              {estimate.seconds != null ? (
                <span className="text-text">
                  <Value>{`~${formatDuration(estimate.seconds)}`}</Value>{" "}
                  <span className="text-secondary">
                    {estimate.basis === "measured"
                      ? t("setup.estimate.fromRuns")
                      : t("setup.estimate.fromCalibration")}
                    {device ? (
                      <>
                        {" · "}
                        <Value>{device}</Value>
                      </>
                    ) : null}
                  </span>
                </span>
              ) : (
                <span className="text-secondary">{t("setup.estimate.unknown")}</span>
              )}
            </span>
            {estimate.basis !== "measured" ? (
              <Button
                variant="ghost"
                onClick={() => calibrate.mutate()}
                disabled={calibrate.isPending}
                title={t("setup.estimate.calibrateHint")}
              >
                {calibrate.isPending ? t("setup.estimate.calibrating") : t("setup.estimate.calibrate")}
              </Button>
            ) : null}
          </>
        ) : (
          <span className="text-secondary">{t("setup.estimate.none")}</span>
        )}
      </div>
      {spec.warnings.length > 0 ? (
        <ul aria-label={t("setup.warnings.label")} className="flex flex-col gap-0.5 border-t border-rule-subtle px-4 py-1.5 text-dense">
          {spec.warnings.map((warning, i) => {
            const Icon = warning.severity === "error" ? CircleAlert : TriangleAlert;
            const objectId = warning.object_id;
            return (
              <li key={`${warning.code}-${i}`} className="flex items-center gap-2">
                <Icon
                  size={14}
                  aria-hidden
                  className={cx("shrink-0", warning.severity === "error" ? "text-error" : "text-warn")}
                />
                <span className="text-text">
                  <WarningText warning={warning} objectName={objectName(objectId)} />
                </span>
                {objectId ? (
                  <button
                    type="button"
                    className="text-accent-ink underline"
                    onClick={() => onSelect(objectId)}
                  >
                    {t("setup.warnings.show")}
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
