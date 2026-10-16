import type { ReactNode } from "react";
import { Trans, useTranslation } from "react-i18next";
import { NetworkError, ServerError } from "../api/client";
import { Cmd } from "../components/Cmd";
import { ErrorPanel } from "../components/ErrorPanel";

interface LoadErrorProps {
  error: unknown;
  onRetry?: () => void;
  actions?: ReactNode;
}

/** The error state of a screen whose query failed (401 never gets here: it ends the session). */
export function LoadError({ error, onRetry, actions }: LoadErrorProps) {
  const { t } = useTranslation();
  let body: ReactNode;
  let detail: string | undefined;
  if (error instanceof NetworkError) {
    body = <Trans i18nKey="errors.network" components={{ cmd: <Cmd /> }} />;
  } else if (error instanceof ServerError) {
    body = t("errors.server", { status: error.status });
    detail = error.code;
  } else {
    detail = String(error);
  }
  return (
    <ErrorPanel title={t("errors.loadFailed")} detail={detail} onRetry={onRetry} actions={actions}>
      {body}
    </ErrorPanel>
  );
}
