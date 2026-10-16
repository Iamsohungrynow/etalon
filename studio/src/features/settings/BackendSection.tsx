import { Trans, useTranslation } from "react-i18next";
import { useSystem } from "../../api/queries";
import { deviceLabel } from "../../app/backend";
import { Cmd } from "../../components/Cmd";
import { Select, type SelectOption } from "../../components/Select";
import { Skeleton } from "../../components/Skeleton";
import { Value } from "../../components/Value";
import { formatBytes } from "../../format/numbers";
import { SettingsSection } from "./SettingsSection";

interface BackendSectionProps {
  value: string;
  onChange: (value: string) => void;
  error: string | null;
}

/** Spec §5.7: backend (auto / cpu / cuda:N) with the detected devices and their memory. */
export function BackendSection({ value, onChange, error }: BackendSectionProps) {
  const { t, i18n } = useTranslation();
  const system = useSystem();
  const devices = system.data?.devices ?? [];
  const options: SelectOption<string>[] = [
    { value: "auto", label: t("settings.backend.auto") },
    { value: "cpu", label: t("settings.backend.cpu") },
    ...devices.map((device) => ({
      value: `cuda:${device.index}`,
      label: <Value>{deviceLabel(device, i18n.language)}</Value>,
    })),
  ];
  if (!options.some((option) => option.value === value)) {
    options.push({
      value,
      label: (
        <>
          <Value>{value}</Value> {t("settings.backend.notFound")}
        </>
      ),
    });
  }

  let devicesBlock;
  if (system.isPending) {
    devicesBlock = (
      <p role="status" className="flex items-center gap-2 text-dense text-secondary">
        <Skeleton width="8rem" /> {t("settings.backend.detecting")}
      </p>
    );
  } else if (devices.length > 0) {
    devicesBlock = (
      <dl className="grid grid-cols-[max-content_max-content_max-content] gap-x-6 gap-y-1 text-dense">
        <dt className="micro-label">{t("settings.backend.devices")}</dt>
        <dt className="micro-label">{t("settings.backend.memory")}</dt>
        <dt className="micro-label">{t("settings.backend.compute")}</dt>
        {devices.map((device) => (
          <div key={device.index} className="contents">
            <dd>
              <Value>{`cuda:${device.index} · ${device.name}`}</Value>
            </dd>
            <dd>
              <Value>{formatBytes(device.memory_bytes, i18n.language)}</Value>
            </dd>
            <dd>
              <Value>{device.compute_capability}</Value>
            </dd>
          </div>
        ))}
      </dl>
    );
  } else {
    const status = system.data?.cupy_status;
    devicesBlock = (
      <div className="flex flex-col gap-1 text-dense text-secondary">
        <p>
          {status === "missing" ? (
            <Trans i18nKey="settings.backend.cupyMissing" components={{ cmd: <Cmd /> }} />
          ) : status === "error"
              ? t("settings.backend.cupyError")
              : t("settings.backend.noDevice")}
        </p>
        {system.data?.cupy_detail ? (
          <Value className="text-muted break-all">{system.data.cupy_detail}</Value>
        ) : null}
      </div>
    );
  }

  return (
    <SettingsSection label={t("settings.backend.label")} help={t("settings.backend.help")} error={error}>
      <Select label={t("settings.backend.label")} value={value} options={options} onValueChange={onChange} />
      {devicesBlock}
    </SettingsSection>
  );
}
