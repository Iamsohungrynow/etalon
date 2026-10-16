import { Play, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useDocumentTitle } from "../../app/useDocumentTitle";
import { Banner } from "../../components/Banner";
import { Button } from "../../components/Button";
import { Chart } from "../../components/Chart";
import { ColorScale } from "../../components/ColorScale";
import { EmptyState } from "../../components/EmptyState";
import { ErrorPanel } from "../../components/ErrorPanel";
import { FieldCanvas } from "../../components/FieldCanvas";
import { IconButton } from "../../components/IconButton";
import { Inspector } from "../../components/Inspector";
import { LogView } from "../../components/LogView";
import { NumberField } from "../../components/NumberField";
import { ProgressBar } from "../../components/ProgressBar";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Skeleton } from "../../components/Skeleton";
import { TabPanel } from "../../components/TabPanel";
import { Table } from "../../components/Table";
import { Tabs } from "../../components/Tabs";
import { TextField } from "../../components/TextField";
import { Toggle } from "../../components/Toggle";
import { Tree } from "../../components/Tree";
import { Value } from "../../components/Value";
import { Viewport3D } from "../../components/Viewport3D";
import { structureTree } from "../setup/structureTree";
import { KitchenSection as Section } from "./KitchenSection";
import { cylindricalPattern, lorentzian, TEST_PREVIEW } from "./samples";

/** `/kitchen-sink`: every design-system component in its states (plan-u1 §4). */
export function KitchenSinkScreen() {
  const { t } = useTranslation();
  useDocumentTitle(t("kitchen.title"));
  const [segment, setSegment] = useState<"dark" | "light" | "system">("dark");
  const [choice, setChoice] = useState("auto");
  const [on, setOn] = useState(true);
  const [wavelength, setWavelength] = useState(1.55);
  const [tab, setTab] = useState<"a" | "b" | "c">("a");
  const [selected, setSelected] = useState<string | null>("structure:0");
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const pattern = useMemo(() => cylindricalPattern(), []);
  const magnitude = useMemo(() => pattern.map(Math.abs), [pattern]);
  const stripOutline = useMemo(() => [{ x0: -4, x1: 4, y0: -0.25, y1: 0.25 }], []);
  const line = useMemo(() => lorentzian(), []);
  const nodes = useMemo(() => structureTree(TEST_PREVIEW, t), [t]);
  const rows = useMemo(
    () => Array.from({ length: 40 }, (_, i) => ({ id: `r${i}`, name: `device_${String(i).padStart(2, "0")}.py`, cells: (i + 1) * 1.25e6 })),
    [],
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b border-rule px-4 py-3">
        <h1 className="text-h2 font-semibold">{t("kitchen.title")}</h1>
        <p className="text-dense text-secondary">{t("kitchen.body")}</p>
      </div>
      <Section title={t("kitchen.buttons")}>
        <Button variant="primary" icon={<Play size={14} aria-hidden />}>{t("kitchen.primary")}</Button>
        <Button>{t("kitchen.secondary")}</Button>
        <Button variant="ghost">{t("kitchen.ghost")}</Button>
        <Button disabled>{t("kitchen.disabled")}</Button>
        <IconButton label={t("kitchen.iconButton")} icon={<RefreshCw size={14} aria-hidden />} />
      </Section>
      <Section title={t("kitchen.inputs")}>
        <TextField label={t("kitchen.text")} defaultValue="ring_r10_g200" mono className="w-64" />
        <TextField label={t("kitchen.textError")} defaultValue="C:\\missing" error={t("kitchen.errorText")} mono className="w-64" />
        <NumberField
          label={t("kitchen.number")}
          value={wavelength}
          quantity="length"
          displayUnit="um"
          onCommit={setWavelength}
          min={0.2}
          max={20}
          step={0.01}
          invalidMessage={t("kitchen.numberInvalid")}
          rangeMessage={t("kitchen.numberRange")}
        />
        <NumberField
          label={t("kitchen.numberNm")}
          value={wavelength}
          quantity="length"
          displayUnit="nm"
          onCommit={setWavelength}
          invalidMessage={t("kitchen.numberInvalid")}
        />
        <Toggle label={t("kitchen.toggle")} checked={on} onCheckedChange={setOn} help={t("kitchen.toggleHelp")} />
        <Segmented
          label={t("kitchen.segmented")}
          value={segment}
          onValueChange={setSegment}
          options={[
            { value: "dark", label: t("settings.theme.dark") },
            { value: "light", label: t("settings.theme.light") },
            { value: "system", label: t("settings.theme.system") },
          ]}
        />
        <Select
          label={t("kitchen.select")}
          value={choice}
          onValueChange={setChoice}
          options={[
            { value: "auto", label: t("settings.backend.auto") },
            { value: "cpu", label: t("settings.backend.cpu") },
          ]}
        />
      </Section>
      <Section title={t("kitchen.tabs")}>
        <div className="w-[36rem]">
          <Tabs
            label={t("kitchen.tabs")}
            value={tab}
            onValueChange={setTab}
            tabs={[
              { value: "a", label: t("results.tabs.fields") },
              { value: "b", label: t("results.tabs.spectra") },
              { value: "c", label: t("results.tabs.sparams"), disabled: true, hint: t("results.tabs.sparamsHint") },
            ]}
          >
            <TabPanel value="a">
              <p className="px-3 py-3 text-dense text-secondary">{t("kitchen.panelA")}</p>
            </TabPanel>
            <TabPanel value="b">
              <p className="px-3 py-3 text-dense text-secondary">{t("kitchen.panelB")}</p>
            </TabPanel>
          </Tabs>
        </div>
      </Section>
      <Section title={t("kitchen.treeInspector")}>
        <div className="w-60 border border-rule bg-surface">
          <Tree
            label={t("setup.tree.label")}
            nodes={nodes}
            selectedId={selected}
            onSelect={setSelected}
            hiddenIds={hidden}
            onToggleHidden={(id) =>
              setHidden((prev) => {
                const next = new Set(prev);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                return next;
              })
            }
            hideLabel={t("setup.tree.hide")}
            showLabel={t("setup.tree.show")}
          />
        </div>
        <div className="w-72">
          <Inspector
            rows={[
              { key: "medium", label: t("setup.inspector.medium"), value: <Value>{TEST_PREVIEW.media[0]?.name}</Value> },
              { key: "index", label: t("setup.inspector.index"), value: <Value>{TEST_PREVIEW.media[0]?.n}</Value> },
              { key: "size", label: t("setup.inspector.size"), value: <Value>{`${TEST_PREVIEW.structures[0]?.size.slice(0, 2).join(", ")} µm`}</Value> },
            ]}
          />
        </div>
        <div className="h-72 w-[28rem] border border-rule">
          <Viewport3D
            label={t("kitchen.viewport")}
            preview={TEST_PREVIEW}
            selectedId={selected}
            hiddenIds={hidden}
            onSelect={setSelected}
            className="h-full w-full"
          />
        </div>
      </Section>
      <Section title={t("kitchen.table")}>
        <div className="flex h-56 w-[32rem] flex-col border border-rule">
          <Table
            label={t("kitchen.table")}
            rows={rows}
            rowKey={(row) => row.id}
            columns={[
              { id: "name", header: t("workspace.columns.name"), width: "minmax(0,1fr)", cell: (row) => <Value>{row.name}</Value> },
              { id: "cells", header: t("workspace.columns.cells"), width: "6rem", align: "end", cell: (row) => <Value>{`${(row.cells / 1e6).toFixed(2)} M`}</Value> },
            ]}
          />
        </div>
      </Section>
      <Section title={t("kitchen.status")}>
        <div className="flex w-[36rem] flex-col gap-2">
          <Banner>{t("workspace.noGpu")}</Banner>
          <Banner tone="warn">{t("results.stale")}</Banner>
          <Banner tone="error">{t("errors.loadFailed")}</Banner>
          <ProgressBar value={0.62} label={t("run.progress")} detail={<Value>{`${18_420} / ${26_400}`}</Value>} />
          <span className="flex items-center gap-2 text-dense text-secondary">
            <Skeleton /> {t("workspace.loading")}
          </span>
        </div>
        <div className="w-80 border border-rule">
          <EmptyState title={t("workspace.empty.title")}>{t("kitchen.emptyBody")}</EmptyState>
        </div>
        <div className="w-80 border border-rule">
          <ErrorPanel title={t("errors.loadFailed")} detail="workspace_missing" onRetry={() => {}} />
        </div>
      </Section>
      <Section title={t("kitchen.log")}>
        <div className="h-40 w-[36rem] border border-rule">
          <LogView
            label={t("run.log.label")}
            lines={[
              { stream: "etalon", line: "grid 184 x 104, dt 1.16e-16 s, CPML 12 layers" },
              { stream: "stdout", line: "2600 steps for 300 fs" },
              { stream: "stderr", line: "UserWarning: an example of stderr" },
            ]}
            emptyText={t("run.log.empty")}
          />
        </div>
      </Section>
      <Section title={t("kitchen.chart")}>
        <div className="h-64 w-[36rem] border border-rule">
          <Chart
            label={t("kitchen.chartLabel")}
            series={[{ name: t("kitchen.chartSeries"), x: line.x, y: line.y }]}
            xLabel={t("results.spectra.x")}
            yLabel={t("kitchen.chartY")}
            tableXHeader={t("results.spectra.x")}
            className="h-full"
          />
        </div>
      </Section>
      <Section title={t("kitchen.field")}>
        <div className="flex h-72 w-[28rem] flex-col border border-rule bg-bg">
          <FieldCanvas
            label={t("kitchen.fieldLabel")}
            data={pattern}
            shape={[160, 120]}
            extent={[-4, 4, -3, 3]}
            colormap="RdBu"
            symmetric
            outlines={stripOutline}
            className="min-h-0 flex-1"
          />
          <div className="border-t border-rule-subtle px-3 py-1.5">
            <ColorScale colormap="RdBu" min={-4.5} max={4.5} scale="linear" label={t("kitchen.fieldScale")} />
          </div>
        </div>
        <div className="flex h-72 w-[28rem] flex-col border border-rule bg-bg">
          <FieldCanvas
            label={t("kitchen.fieldLabel")}
            data={magnitude}
            shape={[160, 120]}
            extent={[-4, 4, -3, 3]}
            colormap="viridis"
            className="min-h-0 flex-1"
          />
          <div className="border-t border-rule-subtle px-3 py-1.5">
            <ColorScale colormap="viridis" min={0} max={4.5} scale="linear" label={t("kitchen.fieldScale")} />
          </div>
        </div>
      </Section>
    </div>
  );
}
