import { useTranslation } from "react-i18next";
import { useSettings, useSystem, useWorkspace } from "../api/queries";
import { Skeleton } from "../components/Skeleton";
import { Value } from "../components/Value";
import { formatBytes } from "../format/numbers";
import { resolveBackend } from "./backend";
import { StripItem } from "./StripItem";

/**
 * The static bottom strip that replaced the reference's tickers (plan-u0 §2): real values
 * only, nothing moves. Skeletons show while a value loads; the GPU probe can take seconds.
 */
export function StatusStrip() {
  const { t, i18n } = useTranslation();
  const system = useSystem();
  const settings = useSettings();
  const workspace = useWorkspace();
  const backend = settings.data && system.data ? resolveBackend(settings.data.backend, system.data) : null;
  const count = workspace.data?.simulations.length;
  return (
    <footer
      aria-label={t("strip.label")}
      className="flex items-center gap-4 overflow-hidden border-t border-rule bg-surface px-4 text-label whitespace-nowrap"
    >
      <StripItem label={t("strip.backend")}>
        {backend ? (
          <Value>
            {backend.id}
            {backend.device
              ? ` · ${backend.device.name} · ${formatBytes(backend.device.memory_bytes, i18n.language)}`
              : ""}
          </Value>
        ) : (
          <>
            <Skeleton width="4rem" /> <span className="text-muted">{t("strip.detecting")}</span>
          </>
        )}
      </StripItem>
      <StripItem label={t("strip.workspace")} grow>
        {settings.data ? (
          <Value title={settings.data.workspace}>{settings.data.workspace}</Value>
        ) : (
          <Skeleton width="10rem" />
        )}
      </StripItem>
      <StripItem>
        {count === undefined ? (
          <Skeleton width="3rem" />
        ) : (
          <>
            <Value>{count}</Value>{" "}
            <span className="micro-label">{t("strip.simulations", { count })}</span>
          </>
        )}
      </StripItem>
      <StripItem label={t("strip.version")}>
        {system.data ? <Value>{system.data.etalon_version}</Value> : <Skeleton width="2.5rem" />}
      </StripItem>
      <span title={t("strip.offlineHint")} className="micro-label shrink-0 text-ok">
        {t("strip.offline")}
      </span>
    </footer>
  );
}
