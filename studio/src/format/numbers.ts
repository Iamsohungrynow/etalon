/**
 * Numbers as Studio prints them (ui-ux-spec §6): SI prefixes, 4 significant figures by
 * default, units always shown. These strings are data, rendered inside <Value>.
 */

const PREFIXES = [
  { exponent: 12, symbol: "T" },
  { exponent: 9, symbol: "G" },
  { exponent: 6, symbol: "M" },
  { exponent: 3, symbol: "k" },
] as const;

function significant(value: number, locale: string, digits: number): string {
  return new Intl.NumberFormat(locale, { maximumSignificantDigits: digits }).format(value);
}

/** The prefix whose scaled value, once rounded, is at least 1 (999 950 → "1 M", not "1000 k"). */
function withPrefix(value: number, locale: string, digits: number, unit: string): string {
  for (const { exponent, symbol } of PREFIXES) {
    const scaled = value / 10 ** exponent;
    if (Math.abs(Number(scaled.toPrecision(digits))) >= 1) {
      return `${significant(scaled, locale, digits)} ${symbol}${unit}`;
    }
  }
  return `${significant(value, locale, digits)}${unit ? ` ${unit}` : ""}`;
}

/** 42 300 000 → "42.3 M"; 11 000 → "11 k"; 512 → "512". */
export function formatCount(value: number, locale = "en", digits = 4): string {
  return withPrefix(value, locale, digits, "");
}

/** Decimal bytes, as GPU memory is sold: 8 585 216 000 → "8.585 GB". */
export function formatBytes(bytes: number, locale = "en", digits = 4): string {
  return withPrefix(bytes, locale, digits, "B");
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** Wall time: 42 → "42s", 192 → "3m12", 3840 → "1h04m". */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total}s`;
  if (total < 3600) return `${Math.floor(total / 60)}m${pad2(total % 60)}`;
  const minutes = Math.round(total / 60);
  return `${Math.floor(minutes / 60)}h${pad2(minutes % 60)}m`;
}

/** Time left, coarser: 45 → "~45s", 130 → "~2m", 3840 → "~1h04m". */
export function formatEta(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `~${total}s`;
  if (total < 3600) return `~${Math.round(total / 60)}m`;
  const minutes = Math.round(total / 60);
  return `~${Math.floor(minutes / 60)}h${pad2(minutes % 60)}m`;
}
