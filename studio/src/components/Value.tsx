import type { ReactNode } from "react";
import { cx } from "./cx";

interface ValueProps {
  /** Optional only so `<Trans components={{ v: <Value /> }}>` can fill it in. */
  children?: ReactNode;
  /** JetBrains Mono with tabular figures (default); false keeps the UI font. */
  mono?: boolean;
  /** Full precision or the full path, shown on hover. */
  title?: string;
  lang?: string;
  className?: string;
}

/**
 * Data, not words: file names, paths, numbers with units, device names. Marked
 * translate="no" so neither i18n nor a browser translator touches it.
 */
export function Value({ children, mono = true, title, lang, className }: ValueProps) {
  return (
    <span
      translate="no"
      title={title}
      lang={lang}
      className={cx(mono && "font-mono tabular-nums", className)}
    >
      {children}
    </span>
  );
}
