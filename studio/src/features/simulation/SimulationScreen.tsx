import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { useWorkspace } from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { useDocumentTitle } from "../../app/useDocumentTitle";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { ErrorPanel } from "../../components/ErrorPanel";
import { Skeleton } from "../../components/Skeleton";
import { Value } from "../../components/Value";

interface SimulationScreenProps {
  view: "setup" | "run" | "results";
}

/**
 * /sim/:id/{setup,run,results}. U0 resolves the id and names the script; the screens
 * themselves arrive in U1 (Setup), U2 (Run) and U3 (Results).
 */
export function SimulationScreen({ view }: SimulationScreenProps) {
  const { t } = useTranslation();
  const { id } = useParams();
  const workspace = useWorkspace();
  const row = workspace.data?.simulations.find((r) => r.id === id);
  useDocumentTitle(row?.name ?? t("notYet.title"));
  const back = (
    <Button asChild icon={<ArrowLeft size={14} aria-hidden />}>
      <Link to="/">{t("simulation.back")}</Link>
    </Button>
  );

  if (workspace.isPending) {
    return (
      <div role="status" className="flex items-center gap-3 px-4 py-4 text-body text-secondary">
        <Skeleton width="12rem" /> {t("workspace.loading")}
      </div>
    );
  }
  if (workspace.isError) {
    return <LoadError error={workspace.error} onRetry={() => void workspace.refetch()} actions={back} />;
  }
  if (!row) {
    return (
      <ErrorPanel title={t("simulation.notFound")} detail={id} actions={back}>
        {t("simulation.notFoundHint")}
      </ErrorPanel>
    );
  }
  return (
    <section className="h-full overflow-y-auto">
      <div className="flex items-baseline gap-3 border-b border-rule px-4 py-3">
        <h1 className="text-h2 font-semibold">
          <Value>{row.name}</Value>
        </h1>
        <Value className="text-dense text-muted">{row.path}</Value>
      </div>
      <EmptyState title={t("notYet.title")} action={back}>
        {t(`notYet.${view}`)}
      </EmptyState>
    </section>
  );
}
