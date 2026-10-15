// V1, V2: the two catalogues match, and every key the code uses exists.
// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import en from "./en.json";
import { latinOutsideTerms } from "./latinTerms";
import zhCN from "./zh-CN.json";

type Catalog = { [key: string]: string | Catalog };

function flatten(catalog: Catalog, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(catalog)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out[path] = value;
    else Object.assign(out, flatten(value, path));
  }
  return out;
}

const PLURAL = /_(zero|one|two|few|many|other)$/;
const enFlat = flatten(en);
const zhFlat = flatten(zhCN);
const baseKeys = (flat: Record<string, string>) =>
  [...new Set(Object.keys(flat).map((k) => k.replace(PLURAL, "")))].sort();
/** The form that carries every placeholder: "_other" for plurals. */
const formOf = (flat: Record<string, string>, base: string) => flat[base] ?? flat[`${base}_other`] ?? "";
const placeholders = (text: string) =>
  [...text.matchAll(/\{\{\s*(\w+)\s*\}\}|<(\/?\w+)>/g)].map((m) => m[1] ?? m[2]).sort();

/** Same text in both languages on purpose: brand, product and technical names. */
const SAME_IN_BOTH = new Set([
  "app.brandName",
  "app.brandProduct",
  "app.documentTitle",
  "strip.version",
  "settings.backend.cpu",
  "settings.about.python",
]);

describe("V1: catalogues", () => {
  it("have the same keys (plural forms aside)", () => {
    expect(baseKeys(zhFlat)).toEqual(baseKeys(enFlat));
  });

  it("have no empty strings", () => {
    for (const [key, value] of [...Object.entries(enFlat), ...Object.entries(zhFlat)]) {
      expect(value.trim(), key).not.toBe("");
    }
  });

  it("use the same placeholders and tags", () => {
    for (const base of baseKeys(enFlat)) {
      expect(placeholders(formOf(zhFlat, base)), base).toEqual(placeholders(formOf(enFlat, base)));
    }
  });

  it("translate everything that is not a name", () => {
    for (const base of baseKeys(enFlat)) {
      if (SAME_IN_BOTH.has(base)) continue;
      expect(formOf(zhFlat, base), base).not.toBe(formOf(enFlat, base));
    }
  });

  it("keep Chinese text free of Latin words other than technical names", () => {
    for (const [key, value] of Object.entries(zhFlat)) {
      if (SAME_IN_BOTH.has(key.replace(PLURAL, ""))) continue;
      expect(latinOutsideTerms(value), key).toBe("");
    }
  });
});

describe("V2: keys used in the code exist", () => {
  const src = fileURLToPath(new URL("..", import.meta.url));
  const files = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
      entry.isDirectory()
        ? files(join(dir, entry.name))
        : /\.tsx?$/.test(entry.name) && !entry.name.includes(".test.")
          ? [join(dir, entry.name)]
          : [],
    );

  it("finds every literal t() and i18nKey in en.json", () => {
    const used = new Set<string>();
    for (const file of files(src)) {
      const text = readFileSync(file, "utf-8");
      for (const m of text.matchAll(/\bt\(\s*"([\w.]+)"/g)) used.add(m[1] ?? "");
      for (const m of text.matchAll(/i18nKey="([\w.]+)"/g)) used.add(m[1] ?? "");
    }
    expect(used.size).toBeGreaterThan(50);
    const known = new Set(baseKeys(enFlat));
    expect([...used].filter((key) => !known.has(key))).toEqual([]);
  });
});
