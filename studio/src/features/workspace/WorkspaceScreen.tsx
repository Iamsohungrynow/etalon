import { Plus, RefreshCw, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ServerError } from "../../api/client";
import { useSettings, useSystem, useWorkspace } from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { useDocumentTitle } from "../../app/useDocumentTitle";
import { Banner } from "../../components/Banner";
import { Button } from "../../components/Button";
import { Cmd } from "../../components/Cmd";
import { EmptyState } from "../../components/EmptyState";
import { ErrorPanel } from "../../components/ErrorPanel";
import { IconButton } from "../../components/IconButton";
import { Skeleton } from "../../components/Skeleton";
import { TextField } from "../../components/TextField";
import { Value } from "../../components/Value";
import { DEMO } from "../../demo/mode";
import { NewSimulationForm } from "./NewSimulationForm";
import { WorkspaceTable } from "./WorkspaceTable";

const SCAN_LIMIT = 5000; // etalon/studio/workspace.py MAX_SCRIPTS

interface WorkspaceScreenProps {
  now?: Date;
}

/** Spec §5.1: every simulation script in the workspace folder, with its last run. */
export function WorkspaceScreen({ now }: WorkspaceScreenProps) {
  const { t } = useTranslation();
  useDocumentTitle(t("workspace.title"));
  const workspace = useWorkspace();
  const system = useSystem();
  const settings = useSettings();
  const [filter, setFilter] = useState("");
  const [creating, setCreating] = useState(false);

  const rows = workspace.data?.simulations;
  const needle = filter.trim().toLowerCase();
  const shown = useMemo(
    () => (rows && needle ? rows.filter((row) => row.path.toLowerCase().includes(needle)) : rows),
    [rows, needle],
  );
  const noGpu = system.data !== undefined && system.data.devices.length === 0;

  let content;
  if (workspace.isPending) {
    content = (
      <div role="status" className="flex flex-col gap-3 px-4 py-4">
        <span className="text-body text-secondary">{t("workspace.loading")}</span>
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} width={`${40 + ((i * 13) % 45)}%`} />
        ))}
      </div>
    );
  } else if (workspace.isError && !rows) {
    const error = workspace.error;
    const missing = error instanceof ServerError && error.code === "workspace_missing";
    content = missing ? (
      <ErrorPanel
        title={t("workspace.missing")}
        detail={settings.data?.workspace}
        onRetry={() => void workspace.refetch()}
        actions={
          <Button asChild>
            <Link to="/settings">{t("workspace.openSettings")}</Link>
          </Button>
        }
      />
    ) : (
      <LoadError error={error} onRetry={() => void workspace.refetch()} />
    );
  } else if (rows && rows.length === 0) {
    content = (
      <>
        <EmptyState
          title={t("workspace.empty.title")}
          action={
            <Button asChild>
              <Link to="/settings">{t("workspace.empty.action")}</Link>
            </Button>
          }
        >
          <Trans i18nKey="workspace.empty.body" components={{ cmd: <Cmd /> }} />
        </EmptyState>
        {creating ? null : <NewSimulationForm />}
      </>
    );
  } else if (shown && shown.length === 0) {
    content = (
      <p className="px-4 py-6 text-body text-secondary">{t("workspace.noMatch", { filter })}</p>
    );
  } else if (shown) {
    content = <WorkspaceTable rows={shown} now={now} />;
  }

  return (
    <section aria-labelledby="workspace-title" className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-4 border-b border-rule px-4 py-2">
        <h1 id="workspace-title" className="shrink-0 text-h2 font-semibold whitespace-nowrap">
          {t("workspace.title")}
        </h1>
        {workspace.data ? (
          <Value className="min-w-0 truncate text-dense text-secondary" title={workspace.data.folder}>
            {workspace.data.folder}
          </Value>
        ) : null}
        <span className="ml-auto" />
        {rows ? (
          <span className="text-dense whitespace-nowrap text-secondary" data-testid="workspace-count">
            {needle && shown
              ? t("workspace.countFiltered", { shown: shown.length, total: rows.length })
              : t("workspace.count", { count: rows.length })}
          </span>
        ) : null}
        <Button
          variant={creating ? "secondary" : "primary"}
          icon={<Plus size={14} aria-hidden />}
          aria-expanded={creating}
          onClick={() => setCreating((open) => !open)}
          disabled={DEMO}
          title={DEMO ? t("demo.needsLocal") : undefined}
        >
          {t("workspace.new.open")}
        </Button>
        <div className="flex items-center gap-1">
          <TextField
            label={t("workspace.filter")}
            hideLabel
            placeholder={t("workspace.filter")}
            icon={<Search size={14} />}
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="w-64"
          />
          {filter ? (
            <IconButton
              label={t("workspace.clearFilter")}
              icon={<X size={14} aria-hidden />}
              onClick={() => setFilter("")}
            />
          ) : null}
          <IconButton
            label={t("workspace.rescan")}
            icon={<RefreshCw size={14} aria-hidden />}
            onClick={() => void workspace.refetch()}
            disabled={workspace.isFetching}
          />
        </div>
      </div>
      {creating ? <NewSimulationForm onCancel={() => setCreating(false)} /> : null}
      {noGpu ? (
        <Banner
          action={
            <Link to="/settings" className="text-dense text-accent-ink underline">
              {t("workspace.noGpuAction")}
            </Link>
          }
        >
          {t("workspace.noGpu")}
        </Banner>
      ) : null}
      {workspace.data?.truncated ? (
        <Banner tone="warn">{t("workspace.truncated", { limit: SCAN_LIMIT })}</Banner>
      ) : null}
      {workspace.isError && rows ? (
        <Banner tone="error">{t("errors.loadFailed")}</Banner>
      ) : null}
      {content}
    </section>
  );
}
