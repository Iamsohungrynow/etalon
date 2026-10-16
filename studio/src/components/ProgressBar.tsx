import { useId, type ReactNode } from "react";

export interface ProgressBarProps {
  /** Fraction done, 0..1 (clamped; NaN counts as 0). */
  value: number;
  /** Accessible name of the bar. */
  label: string;
  /** A line under the bar: step 18 420 / 26 400 · 2:04 elapsed · ~0:55 left. */
  detail?: ReactNode;
}

/** A determinate progress bar: 8 px, a 1 px control outline, an accent fill, no animation. */
export function ProgressBar({ value, label, detail }: ProgressBarProps) {
  const id = useId();
  const fraction = Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(fraction * 100)}
        aria-describedby={detail ? id : undefined}
        className="h-2 border border-control bg-surface"
      >
        <div className="h-full bg-accent" style={{ width: `${Math.round(fraction * 10000) / 100}%` }} />
      </div>
      {detail ? (
        <div id={id} className="text-dense text-secondary">
          {detail}
        </div>
      ) : null}
    </div>
  );
}
