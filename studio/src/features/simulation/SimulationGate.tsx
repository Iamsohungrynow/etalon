import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { SimulationRow } from "../../api/client";
import { LoadError } from "../../app/LoadError";
import { useDocumentTitle } from "../../app/useDocumentTitle";
import { Button } from "../../components/Button";
import { ErrorPanel } from "../../components/ErrorPanel";
import { Skeleton } from "../../components/Skeleton";
import { useSimulationRow } from "./useSimulationRow";

interface SimulationGateProps {
  children: (row: SimulationRow) => ReactNode;
}

/** Resolves `/sim/:id/...` to a workspace row: loading, error and not-found states, then the screen. */
export function SimulationGate({ children }: SimulationGateProps) {
  const { t } = useTranslation();
  const { id, row, workspace } = useSimulationRow();
  useDocumentTitle(row?.title ?? t("simulation.loading"));
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
  if (workspace.isError && !workspace.data) {
    return <LoadError error={workspace.error} onRetry={() => void workspace.refetch()} actions={back} />;
  }
  if (!row) {
    return (
      <ErrorPanel title={t("simulation.notFound")} detail={id} actions={back}>
        {t("simulation.notFoundHint")}
      </ErrorPanel>
    );
  }
  return <>{children(row)}</>;
}
