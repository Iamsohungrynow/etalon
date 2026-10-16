import { FolderOpen } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Trans, useTranslation } from "react-i18next";
import type { Settings } from "../../api/client";
import { useUpdateSettings } from "../../api/queries";
import { Button } from "../../components/Button";
import { Cmd } from "../../components/Cmd";
import { TextField } from "../../components/TextField";
import { DEMO } from "../../demo/mode";
import { SettingsSection } from "./SettingsSection";
import { workspaceErrorMessage } from "./workspaceError";

interface WorkspaceFolderSectionProps {
  settings: Settings;
}

/** The folder Studio lists; the server checks it exists before switching (422 otherwise). */
export function WorkspaceFolderSection({ settings }: WorkspaceFolderSectionProps) {
  const { t } = useTranslation();
  const update = useUpdateSettings();
  const [draft, setDraft] = useState(settings.workspace);
  const [error, setError] = useState<string | null>(null);
  const unchanged = draft.trim() === settings.workspace;

  const apply = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    update.mutate(
      { ...settings, workspace: draft.trim() },
      {
        onSuccess: (saved) => setDraft(saved.workspace),
        onError: (failure) => setError(workspaceErrorMessage(failure, t)),
      },
    );
  };

  return (
    <SettingsSection
      label={t("settings.workspace.label")}
      help={<Trans i18nKey="settings.workspace.help" components={{ cmd: <Cmd /> }} />}
    >
      <form onSubmit={apply} className="flex items-start gap-2">
        <TextField
          label={t("settings.workspace.field")}
          hideLabel
          mono
          icon={<FolderOpen size={14} />}
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setError(null);
          }}
          error={error}
          readOnly={DEMO}
          title={DEMO ? t("demo.needsLocal") : undefined}
          spellCheck={false}
          autoComplete="off"
          className="w-[36rem] max-w-full"
        />
        <Button type="submit" variant="primary" disabled={DEMO || unchanged || update.isPending}>
          {update.isPending ? t("settings.saving") : t("settings.workspace.apply")}
        </Button>
      </form>
    </SettingsSection>
  );
}
