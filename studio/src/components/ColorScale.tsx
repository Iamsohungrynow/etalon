import { useEffect, useRef } from "react";
import { COLORMAP_SIZE } from "../field/colormaps";
import { colormapEntry, formatTick, type ColormapName, type ScaleKind } from "../field/render";
import { cx } from "./cx";
import { Value } from "./Value";

export interface ColorScaleProps {
  colormap: ColormapName;
  /** The limits the field is drawn with (resolveRange), so the bar matches the canvas. */
  min: number;
  max: number;
  scale: ScaleKind;
  /** Unit of the values, shown after the maximum (e.g. "V/m"). */
  unit?: string;
  /** Accessible name, e.g. "Colour scale, |E|". */
  label: string;
  className?: string;
}

/**
 * The colormap as a horizontal 8 px bar with the min, mid and max values under it.
 * Mid is the arithmetic mean for linear and the geometric mean for log, so it sits
 * under the bar's centre either way.
 */
export function ColorScale({ colormap, min, max, scale, unit, label, className }: ColorScaleProps) {
  const barRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const ctx = barRef.current?.getContext("2d");
    if (!ctx) return;
    const image = ctx.createImageData(COLORMAP_SIZE, 1);
    for (let k = 0; k < COLORMAP_SIZE; k++) {
      const [r, g, b] = colormapEntry(colormap, k);
      image.data.set([r, g, b, 255], 4 * k);
    }
    ctx.putImageData(image, 0, 0);
  }, [colormap]);

  const mid = scale === "log" && min > 0 && max > 0 ? Math.sqrt(min * max) : (min + max) / 2;
  return (
    <div role="group" aria-label={label} className={cx("flex flex-col gap-1", className)}>
      <canvas
        ref={barRef}
        width={COLORMAP_SIZE}
        height={1}
        aria-hidden="true"
        className="block h-2 w-full"
      />
      <div className="grid grid-cols-3 text-dense text-secondary">
        <Value className="text-left">{formatTick(min)}</Value>
        <Value className="text-center">{formatTick(mid)}</Value>
        <Value className="text-right">{unit ? `${formatTick(max)} ${unit}` : formatTick(max)}</Value>
      </div>
    </div>
  );
}
