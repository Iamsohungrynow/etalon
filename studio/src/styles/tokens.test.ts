// V3: every text token reaches WCAG AA on bg, surface and raised in both themes.
// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./tokens.css", import.meta.url), "utf-8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no block ${selector}`);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
  return Object.fromEntries(
    [...body.matchAll(/--et-([\w-]+):\s*(#[0-9a-f]{6});/gi)].map((m) => [m[1], m[2]?.toLowerCase()]),
  );
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

const themes = {
  dark: block(':root[data-theme="system"]'),
  light: block(':root[data-theme="light"]'),
};
const TEXT = ["text", "secondary", "muted", "accent-ink", "ok", "warn", "error"];
const SURFACES = ["bg", "surface", "raised"];

describe("V3: design tokens", () => {
  for (const [name, tokens] of Object.entries(themes)) {
    it(`${name}: text colours reach 4.5:1 on every surface`, () => {
      for (const text of TEXT) {
        for (const surface of SURFACES) {
          const ratio = contrast(tokens[text] ?? "", tokens[surface] ?? "");
          expect(ratio, `${text} on ${surface}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    });

    it(`${name}: control outlines and the focus ring reach 3:1`, () => {
      for (const token of ["control", "accent-ink"]) {
        for (const surface of SURFACES) {
          expect(contrast(tokens[token] ?? "", tokens[surface] ?? ""), `${token} on ${surface}`).toBeGreaterThanOrEqual(3);
        }
      }
    });

    it(`${name}: text on an accent fill reaches 4.5:1`, () => {
      expect(contrast(tokens["on-accent"] ?? "", tokens.accent ?? "")).toBeGreaterThanOrEqual(4.5);
    });
  }

  it("the system-light block repeats the light block exactly", () => {
    const media = css.slice(css.indexOf("@media (prefers-color-scheme: light)"));
    const systemLight = Object.fromEntries(
      [...media.matchAll(/--et-([\w-]+):\s*(#[0-9a-f]{6});/gi)].map((m) => [m[1], m[2]?.toLowerCase()]),
    );
    expect(systemLight).toEqual(themes.light);
  });

  it("dark is the default (plain :root)", () => {
    expect(css).toMatch(/:root,\s*:root\[data-theme="dark"\],\s*:root\[data-theme="system"\]/);
  });
});
