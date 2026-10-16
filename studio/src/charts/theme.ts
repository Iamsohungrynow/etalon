/**
 * The design tokens (src/styles/tokens.css, ui-ux-spec §7) as values for canvas and WebGL
 * code: ECharts and three cannot read CSS variables, so they get the resolved colours and
 * re-read them whenever the theme changes.
 */
import { useEffect, useState } from "react";

/** Every `--et-*` colour token, without its prefix. */
export const TOKEN_NAMES = [
  "bg",
  "surface",
  "raised",
  "hover",
  "rule",
  "rule-subtle",
  "control",
  "text",
  "secondary",
  "muted",
  "accent",
  "accent-ink",
  "on-accent",
  "ok",
  "warn",
  "error",
] as const;

export type TokenName = (typeof TOKEN_NAMES)[number];

/**
 * The dark theme's values, used only where no stylesheet is loaded (unit tests in jsdom),
 * so that callers never receive an empty colour. The browser always reads tokens.css.
 */
const DARK_FALLBACK: Record<TokenName, string> = {
  bg: "#0e1013",
  surface: "#15181d",
  raised: "#1c2027",
  hover: "#1c2027",
  rule: "#3a414c",
  "rule-subtle": "#2a2f38",
  control: "#6b7380",
  text: "#eceef2",
  secondary: "#a6adba",
  muted: "#858d9a",
  accent: "#e8b34a",
  "accent-ink": "#e8b34a",
  "on-accent": "#0e1013",
  ok: "#4cc38a",
  warn: "#e8b34a",
  error: "#ec5d62",
};

/** The `--et-*` CSS variables of <html>, resolved for the current theme: `{ bg: "#0e1013", … }`. */
export function readTokens(): Record<string, string> {
  const style = getComputedStyle(document.documentElement);
  const tokens: Record<string, string> = {};
  for (const name of TOKEN_NAMES) {
    tokens[name] = style.getPropertyValue(`--et-${name}`).trim() || DARK_FALLBACK[name];
  }
  return tokens;
}

/** A token by name, never empty. */
export function token(tokens: Record<string, string>, name: TokenName): string {
  return tokens[name] || DARK_FALLBACK[name];
}

/** Relative luminance (WCAG 2) of a #rrggbb colour; NaN for anything else. */
function luminance(hex: string): number {
  const match = /^#([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match?.[1]) return Number.NaN;
  const value = parseInt(match[1], 16);
  const [r, g, b] = [value >> 16, (value >> 8) & 0xff, value & 0xff].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

/**
 * Whether the resolved tokens are the dark palette. Decided from the background itself, so
 * `data-theme="system"` follows the OS exactly as the stylesheet does.
 */
export function isDarkTokens(tokens: Record<string, string>): boolean {
  const l = luminance(token(tokens, "bg"));
  return Number.isNaN(l) || l < 0.5;
}

/**
 * Okabe & Ito (2008), "Color Universal Design": eight colours distinguishable with every
 * common colour-vision deficiency. Order: orange, sky blue, bluish green, yellow, blue,
 * vermillion, reddish purple, black.
 */
export const OKABE_ITO = [
  "#E69F00",
  "#56B4E9",
  "#009E73",
  "#F0E442",
  "#0072B2",
  "#D55E00",
  "#CC79A7",
  "#000000",
] as const;

/** Black does not show on the dark theme's near-black background; grey takes its place. */
const DARK_BLACK = "#999999";

/** The categorical palette for a theme: Okabe–Ito, with #999999 for black on dark. */
export function categoricalPalette(dark: boolean): string[] {
  return OKABE_ITO.map((colour) => (dark && colour === "#000000" ? DARK_BLACK : colour));
}

/** Colour `index` of the palette, wrapping after eight. */
export function seriesColor(index: number, dark: boolean): string {
  const palette = categoricalPalette(dark);
  const i = ((Math.trunc(index) % palette.length) + palette.length) % palette.length;
  return palette[i] ?? DARK_BLACK;
}

/**
 * A number that changes whenever the resolved theme may have changed: `<html data-theme>`
 * is set (Settings), or the OS flips prefers-color-scheme (which `data-theme="system"`
 * follows). Use it as a dependency to re-read the tokens.
 */
export function useThemeVersion(): number {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    const observer = new MutationObserver(bump);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    const media =
      typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-color-scheme: dark)")
        : null;
    media?.addEventListener?.("change", bump);
    return () => {
      observer.disconnect();
      media?.removeEventListener?.("change", bump);
    };
  }, []);
  return version;
}
