import { Download } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useFieldSlice, type FieldQuantity, type ResultMeta } from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { Button } from "../../components/Button";
import { ColorScale } from "../../components/ColorScale";
import { EmptyState } from "../../components/EmptyState";
import { FieldCanvas } from "../../components/FieldCanvas";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Skeleton } from "../../components/Skeleton";
import { Toggle } from "../../components/Toggle";
import { Value } from "../../components/Value";
import { resolveRange } from "../../field/render";
import { saveBlob } from "./download";

interface FieldsTabProps {
  meta: ResultMeta;
}

type CanvasHandle = { toPng(scale?: number): Promise<Blob>; resetView(): void };

const QUANTITIES: readonly FieldQuantity[] = ["abs", "real", "imag", "phase"];

/** Spec §5.4 Fields: monitor → component → quantity → wavelength → colour map → canvas. */
export function FieldsTab({ meta }: FieldsTabProps) {
  const { t } = useTranslation();
  const planes = meta.monitors.filter((m) => m.geometry !== "point" && m.shape);
  const [monitorName, setMonitorName] = useState(planes[0]?.name ?? "");
  const monitor = planes.find((m) => m.name === monitorName) ?? planes[0];
  const [component, setComponent] = useState(monitor?.components.includes("Hz") ? "Hz" : (monitor?.components[0] ?? ""));
  const [quantity, setQuantity] = useState<FieldQuantity>("abs");
  const [wavelengthIndex, setWavelengthIndex] = useState(Math.floor((monitor?.wavelengths_um.length ?? 1) / 2));
  const [logScale, setLogScale] = useState(false);
  const [showOutlines, setShowOutlines] = useState(true);
  const [hover, setHover] = useState<{ x: number; y: number; value: number } | null>(null);
  const canvas = useRef<CanvasHandle>(null);

  const field = useFieldSlice(meta.result_id, monitor?.name ?? null, component, quantity, wavelengthIndex);
  const outlines = useMemo(
    () =>
      showOutlines
        ? meta.preview.structures.map((s) => ({
            x0: (s.center[0] ?? 0) - (s.size[0] ?? 0) / 2,
            x1: (s.center[0] ?? 0) + (s.size[0] ?? 0) / 2,
            y0: (s.center[1] ?? 0) - (s.size[1] ?? 0) / 2,
            y1: (s.center[1] ?? 0) + (s.size[1] ?? 0) / 2,
          }))
        : [],
    [meta.preview, showOutlines],
  );

  if (!monitor) {
    return <EmptyState title={t("results.fields.none")}>{t("results.fields.noneHint")}</EmptyState>;
  }

  const signed = quantity === "real" || quantity === "imag" || quantity === "phase";
  const colormap = signed ? "RdBu" : "viridis";
  const scale = !signed && logScale ? "log" : "linear";
  const wavelength = monitor.wavelengths_um[wavelengthIndex];

  const exportPng = async () => {
    const blob = await canvas.current?.toPng(2);
    if (blob) {
      const name = `${meta.simulation_id}_${monitor.name}_${component}_${quantity}_${wavelength ?? ""}um.png`;
      saveBlob(blob, name);
    }
  };

  let view;
  if (field.isPending) {
    view = (
      <div role="status" className="flex flex-1 items-center justify-center gap-2 text-dense text-secondary">
        <Skeleton width="8rem" /> {t("results.fields.loading")}
      </div>
    );
  } else if (field.isError) {
    view = <LoadError error={field.error} onRetry={() => void field.refetch()} />;
  } else {
    const { header, data } = field.data;
    // One range for the image and its colour scale (log: smallest positive value).
    const [lo, hi] = resolveRange(data, { scale, symmetric: signed });
    view = (
      <>
        <FieldCanvas
          ref={canvas}
          label={t("results.fields.label", { component, monitor: monitor.name })}
          data={data}
          shape={[header.shape[0], header.shape[1]] as [number, number]}
          extent={header.extent as [number, number, number, number]}
          colormap={colormap}
          scale={scale}
          symmetric={signed}
          range={[lo, hi]}
          outlines={outlines}
          onHover={setHover}
          className="min-h-0 flex-1"
        />
        <div className="flex items-center gap-4 border-t border-rule-subtle px-3 py-1.5 text-dense">
          <ColorScale
            colormap={colormap}
            min={lo}
            max={hi}
            scale={scale}
            unit={quantity === "phase" ? "rad" : header.unit}
            label={t("results.fields.scale")}
          />
          <span className="ml-auto text-secondary">
            {hover ? (
              <Value>{`x ${hover.x.toFixed(3)} · y ${hover.y.toFixed(3)} µm · ${hover.value.toPrecision(5)}`}</Value>
            ) : (
              t("results.fields.hint")
            )}
          </span>
        </div>
      </>
    );
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_280px]">
      <section aria-label={t("results.fields.stage")} className="flex min-h-0 flex-col bg-bg">
        {view}
      </section>
      <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto border-l border-rule bg-surface px-3 py-3">
        <div className="flex flex-col gap-1">
          <span className="micro-label">{t("results.fields.monitor")}</span>
          <Select
            label={t("results.fields.monitor")}
            value={monitor.name}
            onValueChange={setMonitorName}
            options={planes.map((m) => ({ value: m.name, label: <Value>{m.name}</Value> }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <span className="micro-label">{t("results.fields.component")}</span>
          <Segmented
            label={t("results.fields.component")}
            value={component}
            onValueChange={setComponent}
            options={monitor.components.map((c) => ({ value: c, label: <Value>{c}</Value> }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <span className="micro-label">{t("results.fields.quantity")}</span>
          <Segmented
            label={t("results.fields.quantity")}
            value={quantity}
            onValueChange={setQuantity}
            options={QUANTITIES.map((q) => ({ value: q, label: t(`results.quantity.${q}`) }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <span className="micro-label">{t("results.fields.wavelength")}</span>
          <Select
            label={t("results.fields.wavelength")}
            value={String(wavelengthIndex)}
            onValueChange={(v) => setWavelengthIndex(Number(v))}
            options={monitor.wavelengths_um.map((w, i) => ({
              value: String(i),
              label: <Value>{`${w.toPrecision(4)} µm`}</Value>,
            }))}
          />
        </div>
        <Toggle
          label={t("results.fields.log")}
          checked={!signed && logScale}
          onCheckedChange={setLogScale}
          disabled={signed}
        />
        <Toggle label={t("results.fields.outlines")} checked={showOutlines} onCheckedChange={setShowOutlines} />
        <div className="flex gap-2">
          <Button icon={<Download size={14} aria-hidden />} onClick={() => void exportPng()} disabled={!field.data}>
            {t("results.fields.exportPng")}
          </Button>
          <Button variant="ghost" onClick={() => canvas.current?.resetView()}>
            {t("results.fields.resetView")}
          </Button>
        </div>
      </aside>
    </div>
  );
}
