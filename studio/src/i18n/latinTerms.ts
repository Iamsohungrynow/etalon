/**
 * Latin-script names that stay Latin in Chinese text: the brand and technical terms.
 * Used by the catalogue test (V1) and by Playwright's language check (P4), which both
 * assert that Chinese UI text contains no other Latin words.
 */
export const LATIN_TERMS = [
  "S 参数",
  "DFTMonitor",
  "Courant",
  "CPML",
  "PML",
  "NaN",
  "PNG",
  "CSV",
  "rad",
  "µm",
  "nm",
  "TE",
  "TM",
  "Ex",
  "Ey",
  "Ez",
  "Hx",
  "Hy",
  "Hz",
  "M1",
  "M2",
  "JetBrains Mono",
  "etalon",
  "Etalon",
  "Studio",
  "CUDA",
  "GPU",
  "CPU",
  "CuPy",
  "Python",
  "NVIDIA",
  "JSON",
  "Inter",
  "ID",
] as const;

/** Code (`<cmd>…</cmd>`) and values (`<v>…</v>`) inside a translation are data. */
const TAGGED_DATA = /<(cmd|v)>.*?<\/\1>/g;
const PLACEHOLDER = /\{\{\s*\w+\s*\}\}/g;

/**
 * The Latin words left in `text` once <cmd> code, <v> values, {{placeholders}} and
 * LATIN_TERMS are removed.
 */
export function latinOutsideTerms(text: string): string {
  let rest = text.replace(TAGGED_DATA, "").replace(PLACEHOLDER, "");
  for (const term of LATIN_TERMS) rest = rest.split(term).join("");
  return rest.match(/[A-Za-z]+/g)?.join(" ") ?? "";
}
