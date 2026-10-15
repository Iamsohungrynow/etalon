import { useTranslation } from "react-i18next";
import { useSystem } from "../../api/queries";
import { Skeleton } from "../../components/Skeleton";
import { Value } from "../../components/Value";
import { SettingsSection } from "./SettingsSection";

/** Versions, and the licences that travel with the bundle (plan-u0 D3). */
export function AboutSection() {
  const { t } = useTranslation();
  const system = useSystem();
  const value = (text: string | undefined) => (text ? <Value>{text}</Value> : <Skeleton />);
  const link = "text-accent-ink underline";
  return (
    <SettingsSection label={t("settings.about.label")}>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 text-dense">
        <dt className="text-secondary">{t("settings.about.version")}</dt>
        <dd>{value(system.data?.etalon_version)}</dd>
        <dt className="text-secondary">{t("settings.about.python")}</dt>
        <dd>{value(system.data?.python_version)}</dd>
        <dt className="text-secondary">{t("settings.about.platform")}</dt>
        <dd>{value(system.data?.platform)}</dd>
        <dt className="text-secondary">{t("settings.about.licences")}</dt>
        <dd className="flex flex-wrap gap-x-4">
          <a className={link} href="/licenses/THIRD_PARTY.md" target="_blank" rel="noreferrer">
            {t("settings.about.thirdParty")}
          </a>
          <a className={link} href="/licenses/inter-OFL.txt" target="_blank" rel="noreferrer">
            {t("settings.about.interLicence")}
          </a>
          <a className={link} href="/licenses/jetbrains-mono-OFL.txt" target="_blank" rel="noreferrer">
            {t("settings.about.monoLicence")}
          </a>
        </dd>
      </dl>
    </SettingsSection>
  );
}
