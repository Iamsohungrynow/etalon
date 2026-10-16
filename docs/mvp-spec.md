# etalon MVP specification

Status: draft v0.1 · 2026-10-15 · owner: Martina

## 1. One sentence

Ship a Python package that runs 2D/3D FDTD for passive silicon-photonic devices on one local NVIDIA GPU and matches Meep and Lumerical S-parameters within 1 % on five reference devices.

## 2. Target API (what a user writes)

```python
import numpy as np
import etalon as et

si = et.Medium(n=3.476)
sio2 = et.Medium(n=1.444)

wg = et.PolySlab(
    vertices=[(-5, -0.25), (5, -0.25), (5, 0.25), (-5, 0.25)],
    slab_bounds=(-0.11, 0.11),
    medium=si,
)

wls = np.linspace(1.50, 1.60, 11)

sim = et.Simulation(
    size=(10, 4, 2),
    medium=sio2,
    structures=[wg],
    grid=et.AutoGrid(min_steps_per_wvl=20),
    boundary=et.PML(layers=12),
    sources=[
        et.ModeSource(
            center=(-4, 0, 0), size=(0, 3, 2), wavelength=1.55, bandwidth=0.10, mode_index=0
        )
    ],
    monitors=[
        et.ModePortMonitor(
            name="out", center=(4, 0, 0), size=(0, 3, 2), wavelengths=wls, mode_index=0
        )
    ],
    run_time=2e-12,  # seconds
    backend="cuda",  # or "numpy"
)

result = sim.run()  # -> et.SimulationResult, saved to HDF5
S = result.s_matrix()  # xarray: dims (wavelength, port_in, port_out)
result.plot_field("Ey", z=0)  # matplotlib
```

Design intent: a Tidy3D or Lumerical user should recognise every concept and port a script in one day. Names may resemble theirs; implementation is ours.

## 3. Scope

### In scope
- Geometry: Box, Cylinder, PolySlab (extruded polygon), GDS import (gdstk) with layer→slab mapping
- Media: non-dispersive isotropic; one-pole Lorentz (enough for Si/SiO2/SiN near 1550 nm)
- Grid: uniform; nonuniform (per-axis step lists); subpixel smoothing
- Boundaries: CPML on all faces; PEC/PMC for symmetry
- Sources: point dipole, Gaussian pulse in time, TFSF plane wave (for validation), mode source
- Monitors: DFT field monitor (box/plane), flux monitor, mode port monitor (expansion into FDE modes → S-parameters)
- Mode solver: vector finite-difference FDE on a 2D cross-section, n_eff, group index, field profiles, overlap integrals
- Backends: numpy (reference), cupy (RawKernel CUDA)
- Output: HDF5 + xarray; Touchstone (.sNp) export
- Bench: Meep comparison harness + report

- **etalon Studio**: the local web UI (`etalon studio`) for preview + cost estimate, run monitoring, results viewing/export, mode solver, validation report — specified in full in `docs/ui-ux-spec.md`; bilingual en / zh-CN

### Out of scope (MVP)
Geometry editing / CAD and a script editor in Studio (the Python script stays the source of truth), adjoint/inverse design, multi-GPU, parameter-sweep scheduler, active devices, anisotropic media, periodic/Bloch boundaries, PDK libraries, licensing, cloud, Windows packaging (Linux first; macOS CPU-only is fine).

## 4. Milestones and acceptance criteria

| Milestone | Target | Deliverable | Accepted when |
| --- | --- | --- | --- |
| M0 Skeleton + 2D TE | week 1 | package layout, Pydantic models, uniform Yee grid, 2D TE update (NumPy + CuPy), CPML, point source, DFT monitor | vacuum plane wave: measured phase velocity within 0.5 % of c after dispersion correction; CuPy == NumPy to rtol 1e-5; 2D grid 2000×2000 steps ≥ 200 M cell-updates/s on an RTX 3060-class GPU |
| M1 3D + modes | weeks 2–3 | 3D FDTD, PolySlab + subpixel smoothing, FDE mode solver, mode source, mode port monitor, S-parameters | strip waveguide 500×220 nm: n_eff at 1550 nm within 0.5 % of published value; FDTD propagation phase matches FDE n_eff within 0.5 %; straight-waveguide |S21| ≥ 0.995 |
| M2 Benchmark suite | week 4 | `bench/` with the five devices, Meep harness (separate conda env, subprocess), JSON + markdown report | all five: max |ΔS| < 1 % vs Meep across the band; timing table (etalon GPU, etalon CPU, Meep CPU) |
| M3 Usability | weeks 5–6 | nonuniform grid, Lorentz media, GDS import, HDF5 results, Touchstone export, docs site, five example notebooks | a fresh user follows the docs from install to the ring-resonator spectrum without asking a question; `pytest` green on CPU and GPU |
| M4 Performance pass | weeks 7–8 | shared-memory tiling, fused E/H + CPML kernels, float32 everywhere, DFT on GPU | ≥ 10× wall-clock vs Meep (8 CPU cores) on the ring resonator at equal resolution; memory ≤ 24 GB for a 10×10×3 µm cell at 20 nm |

Studio milestones U0–U4 run in parallel and are gated on the solver milestones (U0 after M0, U1–U2 after M1, U3 after M2, U4 with M3); their acceptance criteria are in `docs/ui-ux-spec.md` §10. Solver and Studio are separate Claude Code sessions.

Gate after M2: if accuracy < 1 % cannot be reached on any device, stop and diagnose before adding features. Correctness first.

## 5. Benchmark devices (match Liu & Poon 2025 where possible)

| Device | Geometry (µm) | Band | Quantity compared |
| --- | --- | --- | --- |
| Straight waveguide | 0.5 × 0.22 strip, 10 long, SiO2 clad | 1.50–1.60 | |S21|, phase |
| 90° bend | radius 5 circular, same strip | 1.50–1.60 | |S21| |
| Directional coupler | gap 0.236, length 20, cosine S-bends 10 long to a 4 pitch (Liu & Poon §3.1) | 1.50–1.60 | |S31|², |S41|² (coupling ratio) |
| 1×2 MMI | width 6, length 33.6 (3Lπ/8, slab index), tapers 0.5 → 1.5 over 5, outputs at ±1.5 | 1.50–1.60 | |S21|², |S31|², imbalance |
| Ring resonator (add–drop) | racetrack: radius 10, gap 0.2, 4 coupling straights, 0.6 side straights (Liu & Poon's coupler) | 1.54–1.56 | resonance λ, FSR, Q, extinction |

Liu & Poon cover only the directional coupler and, as an all-pass racetrack, the ring; the other devices use our own geometry. Exact numbers, tiers (2D effective index and 3D) and gates: `bench/config.yaml` and `docs/plan-bench.md`.

Shared settings (resolution, PML, run time, Courant, band, geometry) are frozen in `bench/config.yaml`, which both the Meep scripts and the etalon side read, so the comparison is one-to-one. Plan: `docs/plan-bench.md`.

## 6. Validation ladder (run before every benchmark)

1. Vacuum: Gaussian pulse, measure arrival at two points → phase velocity vs c, numerical dispersion vs Taflove eq. 4.17
2. 1D slab: dielectric slab reflection/transmission vs Fresnel (analytic)
3. 2D waveguide: inject FDE mode, check n_eff from phase accumulation over 10 µm
4. Energy: total flux in = flux out + absorbed in PML, to 1e-3

## 7. Performance targets (single RTX 4090 / A10-class)

- 3D cell 10 × 10 × 3 µm at 20 nm uniform → 7.5e7 cells; 1 ps run at Courant 0.5 → ~26 k steps; target < 5 min
- Memory: 6 field components float32 + CPML aux + ε → ≈ 40 bytes/cell → 3 GB; DFT accumulators per monitor extra

## 8. Repository layout

```
etalon/                 package (see CLAUDE.md); etalon/studio/ = FastAPI server + built SPA assets
studio/                 the Studio frontend source (pnpm, React, TypeScript) — see docs/ui-ux-spec.md §8
bench/                  comparison harness; bench/meep/ = Meep scripts + env.yaml
docs/                   mkdocs
examples/               01_straight_wg.ipynb … 05_ring.ipynb
tests/                  unit (fast, CPU) · gpu (skipped without CuPy) · validation (slow, nightly)
THIRD_PARTY.md          every dependency (Python and JS) and its license
LICENSE                 Apache-2.0
```

## 9. Open questions (answer before M1)

- [ ] Nonuniform grid: per-axis step lists only, or full auto-mesh from min_steps_per_wvl + refinement near interfaces? (MVP: per-axis lists + simple auto)
- [ ] Mode source injection: total-field/scattered-field style or single-plane with back-reflection monitor? (MVP: TFSF-style on one plane)
- [ ] Which published n_eff reference for the 500 × 220 nm strip do we pin? (candidate: Chrostowski & Hochberg, *Silicon Photonics Design*, Table 3.x)
