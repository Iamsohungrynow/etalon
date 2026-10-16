/**
 * Kitchen-sink inputs. They are labelled analytic test patterns, never presented as
 * solver output (spec §3.3: only real solver data stands for results).
 */
import type { Preview } from "../../api/queries";

/** cos(k r) / sqrt(r): the shape of a 2D cylindrical wave, on a 160 × 120 grid. */
export function cylindricalPattern(nx = 160, ny = 120): Float32Array {
  const data = new Float32Array(nx * ny);
  const k = (2 * Math.PI) / 0.5; // 1/µm
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < ny; j++) {
      const x = -4 + (8 * i) / (nx - 1);
      const y = -3 + (6 * j) / (ny - 1);
      const r = Math.max(Math.hypot(x, y), 0.05);
      data[i * ny + j] = Math.cos(k * r) / Math.sqrt(r);
    }
  }
  return data;
}

/** A Lorentzian line, the shape of a resonance, for the chart sample. */
export function lorentzian(points = 200): { x: number[]; y: number[] } {
  const x: number[] = [];
  const y: number[] = [];
  for (let i = 0; i < points; i++) {
    const wl = 1.5 + (0.1 * i) / (points - 1);
    x.push(wl);
    y.push(1 - 0.9 / (1 + ((wl - 1.55) / 0.002) ** 2));
  }
  return { x, y };
}

/** A 2D test geometry: a strip and a block in oxide, one source, two monitors. */
export const TEST_PREVIEW: Preview = {
  is_2d: true,
  plane_z: 0,
  region: { center: [0, 0, 0], size: [8, 4, 0] },
  pml: { layers: 12, thickness: [0.6, 0.6, 0] },
  background: { n: 1.444, name: "SiO2" },
  media: [{ id: "medium:0", n: 3.476, name: "Si" }],
  structures: [
    { id: "structure:0", name: "strip", kind: "Box", center: [0, 0, 0], size: [8, 0.5, 0.22], medium_id: "medium:0" },
    { id: "structure:1", name: "block", kind: "Box", center: [2, 1.2, 0], size: [1, 0.8, 0.22], medium_id: "medium:0" },
  ],
  sources: [
    { id: "source:0", name: "dipole", kind: "PointSource", center: [-3, 0, 0], component: "Hz", wavelength_um: 1.55, bandwidth_um: 0.2 },
  ],
  monitors: [
    { id: "monitor:field", name: "field", kind: "DFTMonitor", geometry: "plane", center: [0, 0, 0], size: [6, 3, 0], wavelengths_um: [1.55], components: ["Hz"] },
    { id: "monitor:out", name: "out", kind: "DFTMonitor", geometry: "point", center: [3, 0, 0], size: [0, 0, 0], wavelengths_um: [1.55], components: ["Hz"] },
  ],
  grid: { dx: 0.05, dy: 0.05, nx: 184, ny: 104, region_cells: [160, 80], dt_s: 1.16e-16, courant: 0.99, steps: 2600 },
};
