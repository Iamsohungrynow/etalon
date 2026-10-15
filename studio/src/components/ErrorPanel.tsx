import { CircleAlert, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./Button";
import { Value } from "./Value";

export interface ErrorPanelProps {
  title: ReactNode;
  children?: ReactNode;
  /** Technical detail (a path, a status code), shown as data. */
  detail?: string;
  onRetry?: () => void;
  /** More actions next to Retry, e.g. a link to Settings. */
  actions?: ReactNode;
}

/** An error where it happened, with a way forward (spec §6: errors stay inline). */
export function ErrorPanel({ title, children, detail, onRetry, actions }: ErrorPanelProps) {
  const { t } = useTranslation();
  return (
    <div role="alert" className="flex flex-col items-start gap-3 px-4 py-8">
      <h2 className="flex items-center gap-2 text-h3 font-semibold text-text">
        <CircleAlert size={16} aria-hidden className="text-error" />
        {title}
      </h2>
      {children ? <div className="max-w-[70ch] text-body text-secondary">{children}</div> : null}
      {detail ? (
        <Value className="block max-w-full border border-rule-subtle bg-raised px-2 py-1 text-dense break-all">
          {detail}
        </Value>
      ) : null}
      {onRetry || actions ? (
        <div className="flex gap-2">
          {onRetry ? (
            <Button onClick={onRetry} icon={<RefreshCw size={14} aria-hidden />}>
              {t("errors.retry")}
            </Button>
          ) : null}
          {actions}
        </div>
      ) : null}
    </div>
  );
}
