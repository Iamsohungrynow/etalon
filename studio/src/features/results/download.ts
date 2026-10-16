/** Saves a Blob made in the page itself (PNG of a view, CSV of a spectrum) as a file. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** RFC 4180 CSV: a header row, then numbers with full precision. */
export function toCsv(header: readonly string[], rows: readonly (readonly number[])[]): string {
  const lines = [header.join(","), ...rows.map((row) => row.map((v) => String(v)).join(","))];
  return lines.join("\r\n") + "\r\n";
}
