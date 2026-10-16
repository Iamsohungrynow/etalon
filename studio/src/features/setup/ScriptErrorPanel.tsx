import { CircleAlert, FileCode, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ScriptError } from "../../api/queries";
import { Button } from "../../components/Button";
import { cx } from "../../components/cx";
import { Value } from "../../components/Value";

interface ScriptErrorPanelProps {
  error: ScriptError;
  onRetry: () => void;
  onOpenEditor: () => void;
}

/** The script failed before etalon saw a simulation (spec §5.2: traceback with the failing line). */
export function ScriptErrorPanel({ error, onRetry, onOpenEditor }: ScriptErrorPanelProps) {
  const { t } = useTranslation();
  const lines = error.traceback.split("\n");
  const marker = error.line != null ? `line ${error.line}` : null;
  return (
    <div role="alert" className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-6">
      <h2 className="flex items-center gap-2 text-h3 font-semibold">
        <CircleAlert size={16} aria-hidden className="text-error" />
        {t(`setup.scriptError.${error.code}`)}
        {error.line != null ? (
          <span className="text-body font-normal text-secondary">
            {t("setup.scriptError.atLine")} <Value>{error.line}</Value>
          </span>
        ) : null}
      </h2>
      <Value className="block text-body text-text">{error.message}</Value>
      <div className="flex gap-2">
        <Button icon={<FileCode size={14} aria-hidden />} onClick={onOpenEditor}>
          {t("setup.openEditor")}
        </Button>
        <Button icon={<RefreshCw size={14} aria-hidden />} onClick={onRetry}>
          {t("errors.retry")}
        </Button>
      </div>
      {error.traceback ? (
        <section className="flex flex-col gap-1">
          <h3 className="micro-label">{t("setup.scriptError.traceback")}</h3>
          <pre translate="no" className="overflow-x-auto border border-rule-subtle bg-bg p-2 font-mono text-dense leading-5">
            {lines.map((line, i) => (
              <span
                key={i}
                className={cx("block", marker && line.includes(marker) && "bg-raised text-error")}
              >
                {line || " "}
              </span>
            ))}
          </pre>
        </section>
      ) : null}
      {error.stdout_tail ? (
        <section className="flex flex-col gap-1">
          <h3 className="micro-label">{t("setup.scriptError.output")}</h3>
          <pre translate="no" className="overflow-x-auto border border-rule-subtle bg-bg p-2 font-mono text-dense leading-5 text-secondary">
            {error.stdout_tail}
          </pre>
        </section>
      ) : null}
    </div>
  );
}
