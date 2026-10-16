import { useQueryClient } from "@tanstack/react-query";
import { BarChart3, Play, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { SimulationRow } from "../../api/client";
import { queryKeys, useCancelJob, useRunSimulation, useSpec } from "../../api/queries";
import { Banner } from "../../components/Banner";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { LogView } from "../../components/LogView";
import { ProgressBar } from "../../components/ProgressBar";
import { Value } from "../../components/Value";
import { formatCount, formatDuration, formatEta } from "../../format/numbers";
import { SimulationGate } from "../simulation/SimulationGate";
import { SimulationHeader } from "../simulation/SimulationHeader";
import { EnergyChart } from "./EnergyChart";
import { LiveField } from "./LiveField";
import { RunOutcome } from "./RunOutcome";
import { useJob } from "./useJob";

/** Spec §5.3 Run: progress, energy decay, live field, log, cancel. */
export function RunScreen() {
  return <SimulationGate>{(row) => <Run row={row} />}</SimulationGate>;
}

function Run({ row }: { row: SimulationRow }) {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const run = useRunSimulation();
  const cancel = useCancelJob();
  const spec = useSpec(row.id);
  // The job this screen follows. It outlives the row's job_id, which turns null once the
  // run ends, so the finished, cancelled or failed outcome stays on screen.
  const [jobId, setJobId] = useState<string | null>(row.job_id ?? null);
  const [rowJobId, setRowJobId] = useState(row.job_id ?? null);
  if (row.job_id && row.job_id !== rowJobId) {
    // A run started elsewhere (Setup, another tab): follow it. Adjusting state while
    // rendering is React's pattern for reacting to a changed prop.
    setRowJobId(row.job_id);
    setJobId(row.job_id);
  }
  const [attempt, setAttempt] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const job = useJob(jobId, attempt);
  const latest = job.progress.at(-1);
  const done = job.done;

  // Results exist once the job is done: let the workspace row learn its last_result_id.
  useEffect(() => {
    if (done) void client.invalidateQueries({ queryKey: queryKeys.workspace });
  }, [done, client]);

  const outlines = useMemo(
    () =>
      (spec.data?.preview.structures ?? []).map((s) => ({
        x0: (s.center[0] ?? 0) - (s.size[0] ?? 0) / 2,
        x1: (s.center[0] ?? 0) + (s.size[0] ?? 0) / 2,
        y0: (s.center[1] ?? 0) - (s.size[1] ?? 0) / 2,
        y1: (s.center[1] ?? 0) + (s.size[1] ?? 0) / 2,
      })),
    [spec.data],
  );

  const start = () =>
    run.mutate(row.id, {
      onSuccess: (started) => {
        setJobId(started.job_id);
        setConfirming(false);
      },
    });
  const stop = () => {
    if (!jobId) return;
    if (!confirming && (latest?.elapsed_s ?? 0) > 60) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    cancel.mutate(jobId);
  };

  const live = Boolean(jobId) && !done;
  const actions = live ? (
    <Button icon={<Square size={14} aria-hidden />} onClick={stop} disabled={cancel.isPending}>
      {cancel.isPending ? t("run.cancelling") : t("run.cancel")}
    </Button>
  ) : (
    <Button variant="primary" icon={<Play size={14} aria-hidden />} onClick={start} disabled={run.isPending}>
      {done ? t("run.again") : t("run.start")}
    </Button>
  );

  if (!jobId) {
    return (
      <section className="flex h-full min-h-0 flex-col">
        <SimulationHeader row={row} actions={actions} />
        <EmptyState
          title={t("run.idle.title")}
          action={
            row.last_result_id ? (
              <Button asChild icon={<BarChart3 size={14} aria-hidden />}>
                <Link to={`/sim/${row.id}/results`}>{t("run.idle.lastResults")}</Link>
              </Button>
            ) : undefined
          }
        >
          {t("run.idle.body")}
        </EmptyState>
      </section>
    );
  }

  const total = latest?.total ?? job.started?.total ?? row.total_steps ?? 0;
  const step = latest?.step ?? 0;
  const fraction = done?.status === "done" ? 1 : total > 0 ? step / total : 0;

  return (
    <section className="flex h-full min-h-0 flex-col">
      <SimulationHeader row={row} actions={actions} />
      {confirming ? (
        <Banner
          tone="warn"
          action={
            <span className="flex gap-2">
              <Button onClick={stop}>{t("run.confirm.yes")}</Button>
              <Button variant="ghost" onClick={() => setConfirming(false)}>
                {t("run.confirm.no")}
              </Button>
            </span>
          }
        >
          {t("run.confirm.body", { time: formatDuration(latest?.elapsed_s ?? 0) })}
        </Banner>
      ) : null}
      {job.connection === "lost" && !done ? (
        <Banner
          tone="error"
          action={<Button onClick={() => setAttempt((n) => n + 1)}>{t("run.reconnect")}</Button>}
        >
          {t("run.lost")}
        </Banner>
      ) : null}
      {done ? <RunOutcome row={row} done={done} /> : null}
      <div className="flex flex-col gap-1.5 border-b border-rule px-4 py-3">
        <ProgressBar
          value={fraction}
          label={t("run.progress")}
          detail={
            latest ? (
              <span className="flex flex-wrap gap-x-4 text-dense text-secondary">
                <span>
                  {t("run.step")} <Value className="text-text">{`${formatCount(step, i18n.language)} / ${formatCount(total, i18n.language)}`}</Value>
                </span>
                <span>
                  <Value className="text-text">{formatDuration(latest.elapsed_s)}</Value> {t("run.elapsed")}
                </span>
                {!done ? (
                  <span>
                    <Value className="text-text">{formatEta(latest.eta_s)}</Value> {t("run.left")}
                  </span>
                ) : null}
                <span>
                  <Value className="text-text">{formatCount(latest.cells_per_s, i18n.language, 3)}</Value>{" "}
                  {t("run.rate")}
                </span>
                {job.started ? (
                  <Value>{`${job.started.backend} · ${job.started.device}`}</Value>
                ) : null}
              </span>
            ) : (
              <span className="text-dense text-secondary">
                {job.started ? t("run.preparing") : t("run.connecting")}
              </span>
            )
          }
        />
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-2 border-b border-rule">
        <div className="min-h-0 border-r border-rule">
          <EnergyChart progress={job.progress} />
        </div>
        <LiveField job={job} outlines={outlines} />
      </div>
      <div className="h-48 shrink-0">
        <LogView
          label={t("run.log.label")}
          lines={job.log}
          emptyText={t("run.log.empty")}
          follow
        />
      </div>
    </section>
  );
}
