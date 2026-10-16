import type { Device, SystemInfo } from "../api/client";
import { formatBytes } from "../format/numbers";

export interface ResolvedBackend {
  /** "cuda:0", "cpu", ... */
  id: string;
  device: Device | null;
  /** The setting names a CUDA device this machine does not have. */
  missing: boolean;
}

/** What a run would use now: the setting, with "auto" resolved against the detected GPUs. */
export function resolveBackend(setting: string, system: SystemInfo | undefined): ResolvedBackend {
  const devices = system?.devices ?? [];
  if (setting === "auto") {
    const first = devices[0];
    return first
      ? { id: `cuda:${first.index}`, device: first, missing: false }
      : { id: "cpu", device: null, missing: false };
  }
  if (setting === "cpu") return { id: "cpu", device: null, missing: false };
  const index = Number(setting.slice("cuda:".length));
  const device = devices.find((d) => d.index === index) ?? null;
  return { id: setting, device, missing: device === null };
}

/** "cuda:0 · NVIDIA GeForce RTX 4060 Ti · 8.585 GB" */
export function deviceLabel(device: Device, locale: string): string {
  return `cuda:${device.index} · ${device.name} · ${formatBytes(device.memory_bytes, locale)}`;
}
