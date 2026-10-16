import { Trans, useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { JobState } from "./useJob";
import { ColorScale } from "../../components/ColorScale";
import { FieldCanvas } from "../../components/FieldCanvas";
import { Value } from "../../components/Value";

interface LiveFieldProps {
  job: JobState;
  outlines: { x0: number; x1: number; y0: number; y1: number }[];
}

/** The running solver's Hz, frame by frame (≤ 10 fps, downsampled to ≤ 256²). */
export function LiveField({ job, outlines }: LiveFieldProps) {
  const { t } = useTranslation();
  const snapshot = job.snapshot;
  let body;
  if (job.started && !job.started.snapshots && !snapshot) {
    body = (
      <p className="px-3 py-6 text-dense text-secondary">
        {t("run.live.off")}{" "}
        <Link to="/settings" className="text-accent-ink underline">
          {t("run.live.settings")}
        </Link>
      </p>
    );
  } else if (!snapshot) {
    body = <p className="px-3 py-6 text-dense text-secondary">{t("run.live.waiting")}</p>;
  } else {
    const { header, data } = snapshot;
    const bound = Math.max(Math.abs(header.min), Math.abs(header.max)) || 1;
    body = (
      <>
        <FieldCanvas
          label={t("run.live.label", { component: header.component })}
          data={data}
          shape={[header.shape[0], header.shape[1]] as [number, number]}
          extent={header.extent as [number, number, number, number]}
          colormap="RdBu"
          symmetric
          range={[-bound, bound]}
          outlines={outlines}
          className="min-h-0 flex-1"
        />
        <div className="flex items-center gap-4 border-t border-rule-subtle px-3 py-1.5 text-dense">
          <ColorScale
            colormap="RdBu"
            min={-bound}
            max={bound}
            scale="linear"
            unit={header.unit}
            label={t("run.live.scale")}
          />
          <span className="ml-auto shrink-0 whitespace-nowrap text-secondary">
            {t("run.live.step")} <Value>{header.step}</Value>
            {" · "}
            <Value>{`${header.shape[0]} × ${header.shape[1]}`}</Value>
          </span>
        </div>
      </>
    );
  }
  return (
    <section aria-labelledby="live-title" className="flex min-h-0 flex-col bg-bg">
      <h2 id="live-title" className="micro-label px-3 py-2">
        <Trans
          i18nKey="run.live.title"
          values={{ component: snapshot?.header.component ?? "Hz" }}
          components={{ v: <Value className="normal-case" /> }}
        />
      </h2>
      {body}
    </section>
  );
}
