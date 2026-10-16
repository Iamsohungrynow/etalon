import { BarChart3 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { SimulationRow } from "../../api/client";
import type { JobDone } from "../../api/jobSocket";
import { Banner } from "../../components/Banner";
import { Button } from "../../components/Button";
import { Value } from "../../components/Value";

interface RunOutcomeProps {
  row: SimulationRow;
  done: JobDone;
}

/** How the run ended: finished, cancelled (partial data kept), or failed with a suggestion. */
export function RunOutcome({ row, done }: RunOutcomeProps) {
  const { t } = useTranslation();
  const resultsLink = done.result_id ? (
    <Button asChild variant="primary" icon={<BarChart3 size={14} aria-hidden />}>
      <Link to={`/sim/${row.id}/results`}>{t("run.done.openResults")}</Link>
    </Button>
  ) : undefined;
  if (done.status === "done") {
    return (
      <Banner tone="info" action={resultsLink}>
        {t("run.done.finished")}
      </Banner>
    );
  }
  if (done.status === "cancelled") {
    return (
      <Banner tone="warn" action={resultsLink}>
        {t("run.done.cancelled")}
      </Banner>
    );
  }
  return (
    <div role="alert" className="flex flex-col gap-2 border-b border-rule bg-raised px-4 py-3">
      <p className="text-body font-semibold text-error">{t("run.done.failed")}</p>
      {done.suggestion ? (
        <p className="text-body text-text">{t(`run.suggestion.${done.suggestion}`)}</p>
      ) : null}
      {done.error ? (
        <>
          <Value className="block text-dense text-text">{done.error.message}</Value>
          <pre translate="no" className="max-h-48 overflow-auto border border-rule-subtle bg-bg p-2 font-mono text-dense">
            {done.error.traceback}
          </pre>
        </>
      ) : null}
    </div>
  );
}
