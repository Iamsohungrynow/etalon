import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { ServerError } from "../../api/client";
import { useCreateSimulation, useTemplates, type TemplateId } from "../../api/queries";
import { Button } from "../../components/Button";
import { Select } from "../../components/Select";
import { TextField } from "../../components/TextField";
import { Value } from "../../components/Value";

const NAME_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

interface NewSimulationFormProps {
  onCancel?: () => void;
}

/** Copies a template into the workspace and opens its Setup (spec §5.1 "New from template"). */
export function NewSimulationForm({ onCancel }: NewSimulationFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const templates = useTemplates();
  const create = useCreateSimulation();
  const [template, setTemplate] = useState<TemplateId>("phc_waveguide");
  const [name, setName] = useState("phc_waveguide");
  const [nameTouched, setNameTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const choose = (next: TemplateId) => {
    setTemplate(next);
    if (!nameTouched) setName(next);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!NAME_PATTERN.test(name)) {
      setError(t("workspace.new.bad_name"));
      return;
    }
    setError(null);
    create.mutate(
      { template, name },
      {
        onSuccess: (row) => void navigate(`/sim/${row.id}/setup`),
        onError: (failure) => {
          const code = failure instanceof ServerError ? failure.code : undefined;
          setError(
            code === "exists"
              ? t("workspace.new.exists")
              : code === "bad_name"
                ? t("workspace.new.bad_name")
                : t("workspace.new.failed"),
          );
        },
      },
    );
  };

  const ids = templates.data?.map((entry) => entry.id) ?? [];
  return (
    <form
      onSubmit={submit}
      aria-label={t("workspace.new.title")}
      className="flex flex-wrap items-start gap-4 border-b border-rule bg-surface px-4 py-3"
    >
      <div className="flex flex-col gap-1">
        <span className="micro-label">{t("workspace.new.template")}</span>
        <Select
          label={t("workspace.new.template")}
          value={template}
          onValueChange={choose}
          options={ids.map((id) => ({ value: id, label: t(`templates.${id}.title`) }))}
          disabled={ids.length === 0}
        />
        <p className="max-w-[48ch] text-dense text-secondary">
          {t(`templates.${template}.description`)}
        </p>
      </div>
      <TextField
        label={t("workspace.new.name")}
        mono
        value={name}
        onChange={(event) => {
          setName(event.target.value);
          setNameTouched(true);
          setError(null);
        }}
        error={error}
        help={
          <>
            {t("workspace.new.nameHelp")} <Value>{`${name || "…"}.py`}</Value>
          </>
        }
        spellCheck={false}
        autoComplete="off"
        className="w-72"
      />
      <div className="flex gap-2 pt-[17px]">
        <Button type="submit" variant="primary" icon={<Plus size={14} aria-hidden />} disabled={create.isPending}>
          {create.isPending ? t("workspace.new.creating") : t("workspace.new.create")}
        </Button>
        {onCancel ? (
          <Button variant="ghost" onClick={onCancel}>
            {t("workspace.new.cancel")}
          </Button>
        ) : null}
      </div>
    </form>
  );
}
