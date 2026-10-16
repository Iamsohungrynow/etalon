import type { TFunction } from "i18next";

function sameLocalDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** The full local date and time, for hover (spec §6: full precision on hover). */
export function formatFullDateTime(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "medium" }).format(
    new Date(iso),
  );
}

/** "14:02 today", "yesterday 09:10", else a date, in the active language. */
export function formatLastRun(iso: string, now: Date, locale: string, t: TFunction): string {
  const date = new Date(iso);
  const time = new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(date);
  if (sameLocalDay(date, now)) return t("time.today", { time });
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameLocalDay(date, yesterday)) return t("time.yesterday", { time });
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" }).format(
    date,
  );
}
