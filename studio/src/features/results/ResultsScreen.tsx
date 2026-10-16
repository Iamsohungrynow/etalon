import { Play } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { SimulationRow } from "../../api/client";
import { useResult } from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { Banner } from "../../components/Banner";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { TabPanel } from "../../components/TabPanel";
import { Tabs } from "../../components/Tabs";
import { SimulationGate } from "../simulation/SimulationGate";
import { SimulationHeader } from "../simulation/SimulationHeader";
import { FieldsTab } from "./FieldsTab";
import { ResultMetaBar } from "./ResultMetaBar";
import { SpectraTab } from "./SpectraTab";

type Tab = "fields" | "spectra" | "sparams";

/** Spec §5.4 Results, as far as M0 can feed it: fields and point spectra; S-parameters at M2. */
export function ResultsScreen() {
  return <SimulationGate>{(row) => <Results row={row} />}</SimulationGate>;
}

function Results({ row }: { row: SimulationRow }) {
  const { t } = useTranslation();
  const result = useResult(row.last_result_id);
  const [tab, setTab] = useState<Tab>("fields");
  const runLink = (
    <Button asChild variant="primary" icon={<Play size={14} aria-hidden />}>
      <Link to={`/sim/${row.id}/run`}>{t("results.runAgain")}</Link>
    </Button>
  );

  let body;
  if (!row.last_result_id) {
    body = (
      <EmptyState title={t("results.none.title")} action={runLink}>
        {t("results.none.body")}
      </EmptyState>
    );
  } else if (result.isPending) {
    body = (
      <div role="status" className="flex items-center gap-2 px-4 py-6 text-dense text-secondary">
        <Skeleton width="12rem" /> {t("results.loading")}
      </div>
    );
  } else if (result.isError) {
    body = <LoadError error={result.error} onRetry={() => void result.refetch()} />;
  } else {
    const meta = result.data;
    body = (
      <>
        <ResultMetaBar meta={meta} />
        {meta.stale ? (
          <Banner tone="warn" action={runLink}>
            {t("results.stale")}
          </Banner>
        ) : null}
        {meta.status === "cancelled" ? <Banner tone="warn">{t("results.partial")}</Banner> : null}
        <div className="flex min-h-0 flex-1 flex-col">
          <Tabs
            label={t("results.tabs.label")}
            value={tab}
            onValueChange={setTab}
            tabs={[
              { value: "fields", label: t("results.tabs.fields") },
              { value: "spectra", label: t("results.tabs.spectra") },
              { value: "sparams", label: t("results.tabs.sparams"), disabled: true, hint: t("results.tabs.sparamsHint") },
            ]}
          >
            <TabPanel value="fields">
              <FieldsTab meta={meta} />
            </TabPanel>
            <TabPanel value="spectra">
              <SpectraTab meta={meta} />
            </TabPanel>
          </Tabs>
        </div>
      </>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col">
      <SimulationHeader row={row} />
      {body}
    </section>
  );
}
