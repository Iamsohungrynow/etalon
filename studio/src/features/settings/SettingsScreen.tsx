import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Settings } from "../../api/client";
import { useSettings, useUpdateSettings } from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { useDocumentTitle } from "../../app/useDocumentTitle";
import { Segmented } from "../../components/Segmented";
import { Skeleton } from "../../components/Skeleton";
import { Toggle } from "../../components/Toggle";
import { Value } from "../../components/Value";
import { LANGUAGE_NAMES } from "../../i18n";
import { AboutSection } from "./AboutSection";
import { BackendSection } from "./BackendSection";
import { SettingsSection } from "./SettingsSection";
import { WorkspaceFolderSection } from "./WorkspaceFolderSection";

/** Unit symbols are data, not words. */
const UNIT_SYMBOLS = { um: "µm", nm: "nm" } as const;

/** Spec §5.7. Every change is saved at once; a failure rolls back and says so in place. */
export function SettingsScreen() {
  const { t } = useTranslation();
  useDocumentTitle(t("settings.title"));
  const settings = useSettings();
  const update = useUpdateSettings();
  const [failed, setFailed] = useState<keyof Settings | null>(null);

  let body;
  if (settings.isPending) {
    body = (
      <div role="status" className="flex flex-col gap-3 px-4 py-4">
        <span className="text-body text-secondary">{t("settings.loading")}</span>
        <Skeleton width="40%" />
        <Skeleton width="60%" />
      </div>
    );
  } else if (settings.isError) {
    body = <LoadError error={settings.error} onRetry={() => void settings.refetch()} />;
  } else {
    const current = settings.data;
    const change = <K extends keyof Settings>(field: K, value: Settings[K]) => {
      setFailed(null);
      update.mutate({ ...current, [field]: value }, { onError: () => setFailed(field) });
    };
    const errorFor = (field: keyof Settings) => (failed === field ? t("settings.saveFailed") : null);
    body = (
      <div className="flex max-w-4xl flex-col">
        <BackendSection
          value={current.backend}
          onChange={(value) => change("backend", value)}
          error={errorFor("backend")}
        />
        <WorkspaceFolderSection settings={current} />
        <SettingsSection label={t("settings.language.label")} error={errorFor("language")}>
          <Segmented
            label={t("settings.language.label")}
            value={current.language}
            onValueChange={(value) => change("language", value)}
            options={[
              { value: "system", label: t("settings.language.system") },
              { value: "en", label: <Value mono={false} lang="en">{LANGUAGE_NAMES.en}</Value> },
              {
                value: "zh-CN",
                label: <Value mono={false} lang="zh-CN">{LANGUAGE_NAMES["zh-CN"]}</Value>,
              },
            ]}
          />
        </SettingsSection>
        <SettingsSection label={t("settings.theme.label")} error={errorFor("theme")}>
          <Segmented
            label={t("settings.theme.label")}
            value={current.theme}
            onValueChange={(value) => change("theme", value)}
            options={[
              { value: "dark", label: t("settings.theme.dark") },
              { value: "light", label: t("settings.theme.light") },
              { value: "system", label: t("settings.theme.system") },
            ]}
          />
        </SettingsSection>
        <SettingsSection
          label={t("settings.units.label")}
          help={t("settings.units.help")}
          error={errorFor("units")}
        >
          <Segmented
            label={t("settings.units.label")}
            value={current.units}
            onValueChange={(value) => change("units", value)}
            options={[
              { value: "um", label: <Value>{UNIT_SYMBOLS.um}</Value> },
              { value: "nm", label: <Value>{UNIT_SYMBOLS.nm}</Value> },
            ]}
          />
        </SettingsSection>
        <SettingsSection label={t("settings.snapshots.label")} error={errorFor("live_snapshots")}>
          <Toggle
            label={t("settings.snapshots.label")}
            help={t("settings.snapshots.help")}
            checked={current.live_snapshots}
            onCheckedChange={(value) => change("live_snapshots", value)}
          />
        </SettingsSection>
        <SettingsSection label={t("settings.privacy.label")}>
          <p className="max-w-[70ch] text-body text-text">{t("settings.privacy.body")}</p>
        </SettingsSection>
        <AboutSection />
      </div>
    );
  }

  return (
    <section aria-labelledby="settings-title" className="h-full overflow-y-auto">
      <div className="border-b border-rule px-4 py-3">
        <h1 id="settings-title" className="text-h2 font-semibold">
          {t("settings.title")}
        </h1>
      </div>
      {body}
    </section>
  );
}
