interface SkeletonProps {
  /** CSS width, e.g. "6rem" or "60%". */
  width?: string;
  className?: string;
}

/**
 * A static placeholder block. Always next to text that says what is loading
 * (spec §6: no spinner without text); it does not shimmer (spec §7: no perpetual motion).
 */
export function Skeleton({ width = "6rem", className }: SkeletonProps) {
  return (
    <span
      aria-hidden
      className={`inline-block h-3 bg-raised align-middle ${className ?? ""}`}
      style={{ width }}
    />
  );
}
