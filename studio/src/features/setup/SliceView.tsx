import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { usePermittivity, type Preview } from "../../api/queries";
import { LoadError } from "../../app/LoadError";
import { ColorScale } from "../../components/ColorScale";
import { FieldCanvas } from "../../components/FieldCanvas";
import { Skeleton } from "../../components/Skeleton";
import { Value } from "../../components/Value";
import { useSelection } from "../../state/selection";

interface SliceViewProps {
  simulationId: string;
  sha: string;
  preview: Preview;
}

type Rect = { x0: number; x1: number; y0: number; y1: number };

function boxRect(center: readonly number[], size: readonly number[]): Rect {
  const [cx = 0, cy = 0] = center;
  const [sx = 0, sy = 0] = size;
  return { x0: cx - sx / 2, x1: cx + sx / 2, y0: cy - sy / 2, y1: cy + sy / 2 };
}

/**
 * The solver's own εr on the simulated plane, PML included: what will actually be
 * simulated, not a redraw of the script. A misplaced structure shows up here first.
 */
export function SliceView({ simulationId, sha, preview }: SliceViewProps) {
  const { t } = useTranslation();
  const permittivity = usePermittivity(simulationId, sha, "Ex");
  const hidden = useSelection((s) => s.hidden);
  const [hover, setHover] = useState<{ x: number; y: number; value: number } | null>(null);

  const outlines = useMemo(() => {
    const region = boxRect(preview.region.center, preview.region.size);
    return [
      region,
      ...preview.structures.filter((s) => !hidden.has(s.id)).map((s) => boxRect(s.center, s.size)),
    ];
  }, [preview, hidden]);

  if (permittivity.isPending) {
    return (
      <div role="status" className="flex h-full items-center justify-center gap-2 text-dense text-secondary">
        <Skeleton width="8rem" /> {t("setup.slice.loading")}
      </div>
    );
  }
  if (permittivity.isError) {
    return <LoadError error={permittivity.error} onRetry={() => void permittivity.refetch()} />;
  }
  const { header, data } = permittivity.data;
  const shape = [header.shape[0], header.shape[1]] as [number, number];
  const extent = header.extent as [number, number, number, number];
  return (
    <div className="flex h-full flex-col">
      <FieldCanvas
        label={t("setup.slice.label")}
        data={data}
        shape={shape}
        extent={extent}
        colormap="viridis"
        scale="linear"
        range={[header.min, header.max]}
        outlines={outlines}
        onHover={setHover}
        className="min-h-0 flex-1"
      />
      <div className="flex items-center gap-4 border-t border-rule-subtle px-3 py-1.5 text-dense">
        <ColorScale
          colormap="viridis"
          min={header.min}
          max={header.max}
          scale="linear"
          label={t("setup.slice.scale")}
        />
        <span className="text-secondary">
          {t("setup.slice.pml", { cells: header.pml_cells })}
        </span>
        <span className="ml-auto text-secondary" aria-live="off">
          {hover ? (
            <Value>
              {`x ${hover.x.toFixed(3)} · y ${hover.y.toFixed(3)} µm · εr ${hover.value.toPrecision(4)}`}
            </Value>
          ) : (
            t("setup.slice.hint")
          )}
        </span>
      </div>
    </div>
  );
}
