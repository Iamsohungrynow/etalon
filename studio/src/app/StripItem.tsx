import type { ReactNode } from "react";
import { cx } from "../components/cx";

interface StripItemProps {
  label?: string;
  children: ReactNode;
  /** Take the spare width and truncate first (the workspace path); others keep their size. */
  grow?: boolean;
}

/** One "LABEL value" pair of the status strip. */
export function StripItem({ label, children, grow = false }: StripItemProps) {
  return (
    <span
      className={cx(
        "flex items-center gap-1.5 border-l border-rule-subtle pl-4 first:border-l-0 first:pl-0",
        grow ? "min-w-0 flex-1" : "shrink-0",
      )}
    >
      {label ? <span className="micro-label">{label}</span> : null}
      <span className="min-w-0 truncate text-secondary">{children}</span>
    </span>
  );
}
