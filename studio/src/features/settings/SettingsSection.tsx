import { useId, type ReactNode } from "react";

interface SettingsSectionProps {
  label: string;
  help?: ReactNode;
  /** Shown under the control when saving this setting failed. */
  error?: string | null;
  children: ReactNode;
}

/** One block of Settings: an uppercase mono label, the control, help, an inline error. */
export function SettingsSection({ label, help, error, children }: SettingsSectionProps) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2 border-b border-rule-subtle px-4 py-4">
      <h2 id={id} className="micro-label">
        {label}
      </h2>
      <div className="flex flex-col items-start gap-2">{children}</div>
      {help ? <div className="max-w-[70ch] text-dense text-secondary">{help}</div> : null}
      {error ? (
        <p role="alert" className="text-dense text-error">
          {error}
        </p>
      ) : null}
    </section>
  );
}
