// V5: how numbers, durations and dates print.
import { describe, expect, it } from "vitest";
import { createI18n } from "../i18n";
import { formatBytes, formatCount, formatDuration, formatEta } from "./numbers";
import { formatLastRun } from "./time";

describe("V5: numbers", () => {
  it("uses SI prefixes with 4 significant figures", () => {
    expect(formatCount(42_300_000)).toBe("42.3 M");
    expect(formatCount(11_000)).toBe("11 k");
    expect(formatCount(26_400)).toBe("26.4 k");
    expect(formatCount(123_456_789)).toBe("123.5 M");
    expect(formatCount(512)).toBe("512");
    expect(formatCount(0)).toBe("0");
    expect(formatCount(1_234_567, "en", 2)).toBe("1.2 M");
  });

  it("moves to the next prefix when rounding reaches 1000", () => {
    expect(formatCount(999_950)).toBe("1 M");
    expect(formatCount(999.96)).toBe("1 k");
  });

  it("prints bytes in decimal units, as GPU memory is sold", () => {
    expect(formatBytes(8_585_216_000)).toBe("8.585 GB");
    expect(formatBytes(3.1e9)).toBe("3.1 GB");
    expect(formatBytes(512)).toBe("512 B");
  });

  it("prints wall time and time left", () => {
    expect(formatDuration(42)).toBe("42s");
    expect(formatDuration(192)).toBe("3m12");
    expect(formatDuration(3840)).toBe("1h04m");
    expect(formatEta(45)).toBe("~45s");
    expect(formatEta(130)).toBe("~2m");
    expect(formatEta(3840)).toBe("~1h04m");
  });
});

describe("V5: last run", () => {
  const now = new Date(2026, 9, 16, 15, 30);
  const local = (day: number, h: number, m: number) => new Date(2026, 9, day, h, m).toISOString();

  it("says today and yesterday in English", () => {
    const { t } = createI18n("en");
    expect(formatLastRun(local(16, 14, 2), now, "en", t)).toBe("14:02 today");
    expect(formatLastRun(local(15, 9, 10), now, "en", t)).toBe("yesterday 09:10");
    expect(formatLastRun(local(12, 9, 10), now, "en", t)).toBe("Oct 12, 2026");
  });

  it("and in Chinese", () => {
    const { t } = createI18n("zh-CN");
    expect(formatLastRun(local(16, 14, 2), now, "zh-CN", t)).toBe("今天 14:02");
    expect(formatLastRun(local(15, 9, 10), now, "zh-CN", t)).toBe("昨天 09:10");
    expect(formatLastRun(local(12, 9, 10), now, "zh-CN", t)).toBe("2026年10月12日");
  });
});
