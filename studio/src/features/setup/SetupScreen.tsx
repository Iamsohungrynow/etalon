import { FileCode, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { ServerError, type SimulationRow } from "../../api/client";
import {
  useOpenInEditor,
  useRunSimulation,
  useSettings,
  useSpec,
  type ScriptError,
} from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { Button } from "../../components/Button";
import { Cmd } from "../../components/Cmd";
import { Inspector } from "../../components/Inspector";
import { Segmented } from "../../components/Segmented";
import { Skeleton } from "../../components/Skeleton";
import { Tree } from "../../components/Tree";
import { Viewport3D } from "../../components/Viewport3D";
import { useSelection } from "../../state/selection";
import { SimulationGate } from "../simulation/SimulationGate";
import { SimulationHeader } from "../simulation/SimulationHeader";
import { EstimateBar } from "./EstimateBar";
import { inspectorRows } from "./inspectorRows";
import { ScriptErrorPanel } from "./ScriptErrorPanel";
import { SliceView } from "./SliceView";
import { structureTree } from "./structureTree";

type View = "3d" | "slice";

const SCRIPT_ERROR_CODES: readonly string[] = ["script_error", "script_timeout", "no_simulation"];

/** The 422 ScriptError body of a failed spec request, if that is what it is. */
function asScriptError(error: unknown): ScriptError | null {
  if (!(error instanceof ServerError) || error.status !== 422) return null;
  return error.code && SCRIPT_ERROR_CODES.includes(error.code) ? (error.body as ScriptError) : null;
}

/** Spec §5.2 Setup: tree | stage | inspector over the estimate bar. */
export function SetupScreen() {
  return <SimulationGate>{(row) => <Setup row={row} />}</SimulationGate>;
}

function Setup({ row }: { row: SimulationRow }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const spec = useSpec(row.id);
  const settings = useSettings();
  const run = useRunSimulation();
  const openEditor = useOpenInEditor();
  const { selectedId, hidden, frameRequest, open, select, toggleHidden } = useSelection();
  const [view, setView] = useState<View>("3d");

  useEffect(() => open(row.id), [open, row.id]);

  const preview = spec.data?.preview;
  const nodes = useMemo(() => (preview ? structureTree(preview, t) : []), [preview, t]);
  const lengthUnit = settings.data?.units === "nm" ? "nm" : "um";
  const rows = useMemo(
    () => (preview ? inspectorRows(preview, selectedId, t, lengthUnit, i18n.language) : []),
    [preview, selectedId, t, lengthUnit, i18n.language],
  );
  const hasErrors = spec.data?.warnings.some((w) => w.severity === "error") ?? true;
  const running = row.status === "running";

  const startRun = () =>
    run.mutate(row.id, { onSuccess: () => void navigate(`/sim/${row.id}/run`) });

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.metaKey || event.ctrlKey) return;
      if (event.key === "r" && !hasErrors && !running) startRun();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const objectName = (id: string | null) => {
    if (!id || !preview) return undefined;
    return (
      preview.structures.find((s) => s.id === id)?.name ??
      preview.sources.find((s) => s.id === id)?.name ??
      preview.monitors.find((m) => m.id === id)?.name ??
      undefined
    );
  };

  const actions = (
    <>
      <Button
        variant="ghost"
        icon={<FileCode size={14} aria-hidden />}
        onClick={() => openEditor.mutate(row.id)}
      >
        {t("setup.openEditor")}
      </Button>
      <Button
        variant="primary"
        icon={<Play size={14} aria-hidden />}
        onClick={startRun}
        disabled={hasErrors || running || run.isPending}
        title={running ? t("setup.alreadyRunning") : undefined}
      >
        {t("setup.run")}
      </Button>
    </>
  );

  let body;
  if (spec.isPending) {
    body = (
      <div role="status" className="flex flex-1 flex-col gap-3 px-4 py-6">
        <span className="text-body text-secondary">{t("setup.building")}</span>
        <Skeleton width="40%" />
        <Skeleton width="55%" />
        <Skeleton width="30%" />
      </div>
    );
  } else if (spec.isError) {
    const scriptError = asScriptError(spec.error);
    body = scriptError ? (
      <ScriptErrorPanel
        error={scriptError}
        onRetry={() => void spec.refetch()}
        onOpenEditor={() => openEditor.mutate(row.id)}
      />
    ) : (
      <LoadError error={spec.error} onRetry={() => void spec.refetch()} />
    );
  } else if (preview) {
    body = (
      <>
        <div className="grid min-h-0 flex-1 grid-cols-[240px_minmax(0,1fr)_280px]">
          <aside className="min-h-0 overflow-y-auto border-r border-rule bg-surface">
            <h2 className="micro-label px-3 pt-3 pb-1">{t("setup.tree.label")}</h2>
            <Tree
              label={t("setup.tree.label")}
              nodes={nodes}
              selectedId={selectedId}
              onSelect={select}
              hiddenIds={hidden}
              onToggleHidden={toggleHidden}
              hideLabel={t("setup.tree.hide")}
              showLabel={t("setup.tree.show")}
            />
          </aside>
          <section aria-label={t("setup.stage")} className="flex min-h-0 flex-col bg-bg">
            <div className="flex items-center gap-3 border-b border-rule-subtle px-3 py-1.5">
              <Segmented
                label={t("setup.view.label")}
                value={view}
                onValueChange={setView}
                options={[
                  { value: "3d", label: t("setup.view.3d") },
                  { value: "slice", label: t("setup.view.slice") },
                ]}
              />
              <span className="text-dense text-secondary">
                {view === "3d" ? (
                  <Trans i18nKey="setup.view.hint3d" components={{ cmd: <Cmd /> }} />
                ) : (
                  t("setup.view.hintSlice")
                )}
              </span>
            </div>
            <div className="min-h-0 flex-1">
              {view === "3d" ? (
                <Viewport3D
                  label={t("setup.viewport")}
                  preview={preview}
                  selectedId={selectedId}
                  hiddenIds={hidden}
                  onSelect={select}
                  frameRequest={frameRequest}
                  className="h-full w-full"
                />
              ) : (
                <SliceView simulationId={row.id} sha={spec.data.script_sha256} preview={preview} />
              )}
            </div>
          </section>
          <aside className="min-h-0 overflow-y-auto border-l border-rule bg-surface px-3 py-3">
            <h2 className="micro-label pb-2">{t("setup.inspector.label")}</h2>
            <Inspector rows={rows} emptyText={t("setup.inspector.empty")} />
          </aside>
        </div>
        <EstimateBar spec={spec.data} objectName={objectName} onSelect={select} />
      </>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col">
      <SimulationHeader row={row} actions={actions} />
      {run.isError ? (
        <div role="alert" className="border-b border-rule bg-raised px-4 py-1.5 text-dense text-error">
          {run.error instanceof ServerError && run.error.code === "already_running"
            ? t("setup.alreadyRunning")
            : t("setup.runFailed")}
        </div>
      ) : null}
      {body}
    </section>
  );
}
