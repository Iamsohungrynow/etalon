# Bench plan: etalon vs Meep on the five reference devices

Status: draft for review · 2026-10-16 · the M2 harness of `mvp-spec.md` §4–§5, built ahead of M1

## 1. What this delivers

`bench/run_meep_comparison.py` runs the five reference devices in Meep (subprocess, own conda env) and in etalon, then `bench/report.py` writes `bench/results/<git-sha>.md` and `.json`. Each record has, per device, the max |ΔS| across the band, the gated quantity from `mvp-spec.md` §5, wall time for etalon GPU, etalon CPU and Meep CPU, and the resolution. Every shared number (geometry, band, resolution, PML, Courant, run time) lives once in `bench/config.yaml`, and both sides read it.

The etalon side cannot run the five devices yet. M0 has 2D TE, point sources, DFT monitors and Box only. There is no 3D, PolySlab, mode source, mode port or S-matrix until M1. §3 proposes how the bench handles that. Nothing under `etalon/` changes.

## 2. Findings that shape the plan

**Meep on this machine.** conda-forge publishes `pymeep` (1.35.0, GPL-2.0-or-later) for linux-64/aarch64/ppc64le and osx-64/arm64 only, with no win-64 build (checked on the anaconda.org API, 2026-10-16). Meep's Installation page says native Windows is unsupported and points to Ubuntu under WSL. This machine has WSL2 (only Docker Desktop's internal distro), Docker Desktop 4.78, no conda, a 6-core Ryzen 5 5600, 32 GB RAM (WSL2 gets 16 GB by default, with no `.wslconfig`) and 557 GB free disk.

**Liu & Poon 2025** (arXiv:2506.16665 v3: "Comparison of Lumerical FDTD and Tidy3D for three-dimensional FDTD simulations of passive silicon photonic components", CC BY 4.0) covers only two of our five devices:
- **Directional coupler:** gap 0.236 µm, coupling length 20 µm, port pitch 4 µm, S-bends 10 µm long. Cross-port power was 41–48 % at ≥ 15 cells/λ. Lumerical and Tidy3D differ by 3.7–4.6 %.
- **Ring:** an *all-pass racetrack*, R = 10, gap 0.2, with 4 µm coupling straights, 0.6 µm side straights and Euler bends. Q ≈ 1750–1840, FSR ≈ 7.4–7.6 nm. The two solvers differ by 2 % in Q and 0.6 nm in resonance wavelength.

They also simulate a 2×2 MMI, a crossing, a mode converter and a PSR, but no straight waveguide, 90° bend or 1×2 MMI. All runs are 3D with Palik-fitted dispersive Si/SiO₂, 15–25 cells/λ in Si, and a 1e-5 auto-shutoff. Their repository (JPPhotonics/fdtd-pipeline) has **no licence**, so we take numbers from the paper only, never files.

Their 2–5 % disagreement between two commercial solvers is the context for our 1 % gate. We can only hit 1 % because we compare at equal resolution, equal materials and equal geometry.

**Meep conventions.** These come from meep.readthedocs.io only; no Meep source was opened.
- Units: f = a/λ, with time in a/c = 3.33564 fs for a = 1 µm.
- Time step: cΔt = S·Δx with default S = 0.5. This matches plan-m0 §8, where etalon's courant = S·√D.
- PML lies *inside* `cell_size`. The recommended thickness is about half the largest wavelength, doubled until converged.
- Time dependence is e^(−iωt), the same as etalon.
- `get_eigenmode_coefficients` returns `alpha[band, freq, 0 = forward / 1 = backward]`. Modes are normalised to unit power. MPB's mode phase is "arbitrary (but deterministic)".
- In 2D, the Hz polarisation (Ex, Ey, Hz) is `EVEN_Z`. That equals etalon's 2D TE and the TE-like strip mode. Meep's own 2D waveguide tutorials use Ez/`ODD_Z`, which we must not copy.
- `GaussianSource(f, fwidth)` has the envelope exp(−(t−t0)²/2w²) with w = 1/fwidth and t0 = 5w.

**Cost.** Order-of-magnitude estimates at Δ = 20 nm. They assume etalon at 2e9 cell-updates/s in 3D, Meep at 1.5e8/s on 6 MPI ranks, NumPy at 3e7/s in 2D and 1e7/s in 3D, and ~40 B/cell for etalon vs ~150 B/cell for Meep (double precision). Pilot P5 replaces the Meep figure with a measured one.

| Device (region) | 2D cells | 3D cells, 0.5 µm PML | etalon GPU mem | Meep RAM | Meep 3D time | Fits this machine in 3D? |
| --- | --- | --- | --- | --- | --- | --- |
| straight (12 × 4 × 2.4 µm) | 2e5 | 2.8e7 | 1.1 GB | ~4 GB | ~1.5 h | yes |
| bend (8.4 × 8.4 × 2.4) | 3e5 | 3.8e7 | 1.5 GB | ~6 GB | ~2 h | yes |
| DC (44 × 6.6 × 2.4) | 1e6 | 1.4e8 | 5.8 GB | ~22 GB | ~13 h | GPU yes; Meep needs WSL memory raised |
| MMI (47.6 × 8 × 2.4) | 1.2e6 | 1.9e8 | 7.5 GB | ~28 GB | ~21 h | no (8 GB GPU, 32 GB RAM) |
| ring (30 × 24.6 × 2.4, ~10 ps) | 2e6 | 3.4e8 | 13 GB | ~50 GB | ~1 week | no |

In 2D, every device except the ring takes minutes in Meep. The ring takes about 1 h in Meep and minutes on the GPU. On NumPy the 2D ring takes about 6 h and the others under an hour.

## 3. The etalon side before M1 (decision D2)

| Option | What exists after this work | Cost / risk |
| --- | --- | --- |
| **A.** Meep side, harness and report complete; etalon adapters fail with a clear message | Meep reference data for all devices, frozen and committed; the report lists every device with Meep timing and "needs M1 (ModeSource, ModePortMonitor, PolySlab, 3D)" | Nothing in the bench is checked against etalon until M1 |
| **B. (recommended)** A, plus a device 0, `point2d`, that both sides can run today | Same as A, plus one real Meep-vs-etalon row now | One small extra device |
| C. Write the five etalon adapters now against the API in `mvp-spec.md` §2 | Untestable code | The code will drift from the API M1 actually ships |
| D. Build nothing until M1 | — | The Meep 3D references take hours to days and could be generated now |

`point2d` is a 2D TE Hz line source in SiO₂ with two Hz probes 4 µm apart. It compares the complex transfer ratio T(λ) = Hz(probe 2) / Hz(probe 1). The ratio cancels each code's source normalisation, so it tests exactly the conventions that silently break a cross-code comparison:
- config read on both sides
- µm ↔ Meep units
- courant = S·√D
- PML inside vs outside the region
- grid alignment
- the e^(−iωt) sign

Both codes are standard Yee at the same Δx and Δt, so they share the same numerical dispersion. T should agree to ~1e-5. The gate is 1e-3, and anything above 1e-4 gets investigated before M1. This is a convention check, not a physics device.

Adapters for the five devices check what the installed etalon offers. They look for `et.ModeSource`, `et.ModePortMonitor` and `et.PolySlab`, and for 3D they ask `fdtd.capabilities.check_supported`. They raise `NeedsMilestone("M1", missing=[...])`. The harness catches it, prints it and writes `status: "unsupported"` to `bench/etalon/out/<device>.json`. The M2 session fills in each adapter's `build()` once M1 lands; the contract is in §6.

## 4. Files

```
bench/
  __init__.py              makes bench importable by both environments (shared modules below need numpy, pydantic, pyyaml only)
  config.yaml              THE frozen numbers: materials, tiers, resolution, PML, Courant, band, run time, geometry, ports
  config.py                pydantic schema (extra="forbid": a typo fails), loader, derived values, config hashes
  devices.py               geometry from config: polygons, region, ports, source plane per device (numpy only)
  schema.py                out-JSON models: write, read, validate; S as [re, im]
  metrics.py               derived quantities (|S|², imbalance, coupling ratio, ring λ_res / FSR / Q / ER) and differences
  report.py                compares bench/meep/out and bench/etalon/out → results/<sha>.md and the "meep_comparison" section of results/<sha>.json
  record.py                git sha (+ "-dirty", ignoring bench/results and the out/ dirs), section merge into results/<sha>.json
  run_meep_comparison.py   orchestrator: Meep (subprocess, cached) → etalon cuda + numpy (subprocess) → report; the CLAUDE.md entry point
  plot_devices.py          validation plot: results/bench_devices.png, every layout with ports, source plane and PML drawn
  validate_m0.py           existing; changed only to write its record through record.py (section "m0")
  meep/                    the only place that imports meep; never imported by anything in etalon's env
    env.yaml               conda-forge: pymeep=1.35.0=mpi_mpich_*, python 3.12, numpy, pyyaml, pydantic, mpi4py (pinned)
    env.lock.txt           explicit lock exported after the first install
    run_device.py          config → mp.Simulation → out/<device>.json; run as `python -m mpi4py -m bench.meep.run_device`
    out/<device>.json      reference results, committed with their provenance
  etalon/
    run_device.py          config → et.Simulation → out/<device>.json; point2d now, the five via NeedsMilestone
    out/                   git-ignored
  results/<sha>.md, <sha>.json
tests/bench/               see §10
```

Two import rules, both enforced by a static test (B7):
1. No file outside `bench/meep/` imports `meep`.
2. Nothing in `bench/meep/` imports `etalon`, so the reference is independent.

Running as `python -m bench.meep.run_device` from the repository root keeps `import meep` resolving to pymeep, not to `bench/meep/`.

## 5. Shared configuration: `bench/config.yaml`

Schema, with the proposed values. Every geometric number is in µm, with the region centre on a grid node and every extent an even number of cells, so both codes put the same Yee nodes in the same places. The loader rejects a config that breaks this.

```yaml
schema: 1
materials: {si: 3.476, sio2: 1.444}           # fixed index, mvp-spec §2; dispersive media are M3
strip: {width: 0.5, thickness: 0.22}
tiers:
  2d:
    dims: 2
    core_index: 2.84778        # TE0 effective index of a 0.22 µm Si slab in SiO2 at 1.55 µm (symmetric slab, exact root)
    resolution: 50             # px/µm in both codes: Meep resolution = 50, etalon UniformGrid(dl=0.02)
    pml: 1.0                   # µm; Meep cell = region + 2·pml; etalon PML(layers=50) outside the region
    courant_meep: 0.5          # Meep S; etalon courant = S·√D = 0.7071
    devices: [point2d, straight, bend, dc, mmi, ring]
  3d:
    dims: 3
    resolution: 50
    pml: 0.5                   # 1.0 if pilot P1 shows 0.5 changes S by > 1e-3
    courant_meep: 0.5          # etalon courant 0.8660
    z: [-1.2, 1.2]             # region z extent; 1.09 µm oxide beyond the core ≈ 8.7 decay lengths
    devices: [straight, bend, dc]     # mmi, ring: need ≥ 16 GB GPU and ≥ 64 GB RAM (§2)
ports: {width: 2.5, height: 2.2, mode: 0, source_offset: 0.5}   # mode plane; source 0.5 µm upstream of port 1
etalon: {precision: single, cpu_full_run_max_minutes: 30}
devices:
  point2d:  {medium: sio2, region: {center: [0, 0], size: [8.0, 4.0]}, source: [-2.99, 0.01],
             probes: [[-1.99, 0.01], [2.01, 0.01]], band: [1.50, 1.60, 51], run_time_fs: 300}
  straight: {length: 10.0, region: {center: [0, 0], size: [12.0, 4.0]}, band: [1.50, 1.60, 51], run_time_fs: 1000}
  bend:     {radius: 5.0, shape: circular, region: {center: [2.2, 2.8], size: [8.4, 8.4]},
             band: [1.50, 1.60, 51], run_time_fs: 1000}
  dc:       {gap: 0.236, coupling_length: 20.0, sbend_length: 10.0, pitch: 4.0, sbend: cosine,
             region: {center: [0, 0], size: [44.0, 6.6]}, band: [1.50, 1.60, 51], run_time_fs: 1600}
  mmi:      {width: 6.0, length: 33.6, taper_width: 1.5, taper_length: 5.0, output_offset: 1.5,
             region: {center: [0, 0], size: [47.6, 8.0]}, band: [1.50, 1.60, 51], run_time_fs: 2000}
  ring:     {radius: 10.0, gap: 0.2, straight_x: 4.0, straight_y: 0.6, shape: circular,
             region: {center: [0, 0], size: [30.0, 24.6]}, band: [1.54, 1.56, 401], run_time_fs: 10000}
```

The `run_time_fs` values are placeholders. Pilot P2 sets them so that the field energy at every output port decays to ≤ 1e-5 of its peak (Liu & Poon's shutoff level), and then they are frozen. Port centres, normals and the source plane are derived in `devices.py` (§6), not typed in by hand.

The derived values are computed once in `config.py`, and both sides use them:
- **Meep units:** frequency = 1/λ[µm], `until` = t / 3.33564 fs.
- **Courant:** etalon courant = S·√D.
- **PML:** etalon layers = pml × resolution, which must be an integer.
- **Pulse:** both sides get the same Gaussian envelope and delay. etalon uses `GaussianPulse(λ0, bandwidth)`, with σ_f = (f_hi − f_lo)/2, τ = 1/(2πσ_f) and t0 = 5τ. Meep uses `GaussianSource(f0, fwidth = 2πσ_f·a/c, cutoff = 5)`, so w = τ and t0 = 5τ. For the 1.50–1.60 band this gives fwidth = 0.131, close to the 0.2·fcen the Meep tutorials use. Only the carrier phase differs (sin vs cos), and S does not depend on it.

Each out file records `config_sha256`, a hash of the canonical JSON of that device's resolved spec plus its tier. The report refuses to compare files whose hashes differ.

## 6. Devices and how each maps to both codes

Ports are numbered as in `mvp-spec.md` §5, and port 1 is always driven, along +x. Each port plane holds exactly one strip, centred on it. The outward normal says which Meep coefficient is the outgoing wave: `alpha[...,0]` for a + normal, `alpha[...,1]` for a − normal.

| Device | Geometry (polygons from `devices.py`) | Ports (centre, outward normal) | Compared |
| --- | --- | --- | --- |
| point2d | homogeneous SiO₂; Hz source and probes on Hz nodes | probes at x = −1.99 and +2.01 | complex T(λ) |
| straight | strip along x through the whole region, into the PML | 1 (−5, 0) −x · 2 (+5, 0) +x: 10 µm apart | S21 complex (magnitude and phase) |
| bend | input along y = 0, circular 90° arc of R = 5 about (0, 5), output along x = 5 | 1 (−1, 0) −x · 2 (5, 6) +y | \|S21\| |
| dc | two arms: cosine S-bends (pitch 4 → gap 0.236 over 10 µm), 20 µm coupled section | 1 (−21, −2) −x · 2 (−21, +2) −x · 3 (+21, −2) +x · 4 (+21, +2) +x | \|S31\|², \|S41\|², coupling ratio |
| mmi | 0.5 µm input, linear tapers 0.5 → 1.5 over 5 µm, 6 × 33.6 µm body, outputs at y = ±1.5 | 1 (−22.8, 0) −x · 2 (+22.8, +1.5) +x · 3 (+22.8, −1.5) +x | \|S21\|², \|S31\|², imbalance |
| ring | add–drop racetrack: R = 10 circular quarter arcs, 4 µm coupling straights, 0.6 µm side straights, buses at y = ±11.0 (gap 0.2) | 1 in (−14, −11) −x · 2 through (+14, −11) +x · 3 drop (−14, +11) −x · 4 add (+14, +11) +x | λ_res, FSR, Q, extinction |

In 3D, every polygon is a 0.22 µm slab centred on z = 0 in SiO₂ above and below. In 2D the same polygons become z-invariant with n = `core_index`. The ring is two polygons, the Si outer racetrack and then the SiO₂ inner one. In both codes "later structures win", so the order gives the hole.

| Concept | Meep (public API) | etalon (M1 API, `mvp-spec.md` §2) |
| --- | --- | --- |
| region | `cell_size` = size + 2·pml, `geometry_center` = centre, `boundary_layers=[mp.PML(pml)]` | `Simulation(center, size)`, `PML(layers=pml·res)` outside |
| grid, time step | `resolution=res`, `Courant=S` | `UniformGrid(dl=1/res)`, `courant=S·√D` |
| materials | `mp.Medium(index=n)`, `default_material` = SiO₂, `eps_averaging` on (default) | `Medium(n=n)`, subpixel smoothing per plan-m1 A4 |
| strips | `mp.Prism(vertices, height=0.22, axis=z)`; 2D: `height=mp.inf` | `PolySlab(vertices, slab_bounds=(−0.11, 0.11))` |
| source | `EigenModeSource(GaussianSource(...), center, size, eig_band=1, eig_parity=mp.EVEN_Z, eig_match_freq=True)` | `ModeSource(center, size, mode_index=0, pulse=GaussianPulse(...))` |
| ports | `add_mode_monitor(freqs, FluxRegion(center, size))`, then `get_eigenmode_coefficients(mon, [1], eig_parity=mp.EVEN_Z)` | `ModePortMonitor(name, center, size, wavelengths, mode_index=0)` |
| S | `alpha_i[0, :, out] / alpha_1[0, :, 0]` | `result.s_matrix()` |
| run | `sim.run(until=t·c/a)` | `run_time=t` |
| symmetry | none (keeps the cell, and so the timing, equal) | none |

`EVEN_Z` is exact in 3D because the cladding is symmetric in z. It separates the TE-like modes, and band 1 is TE0. In 2D it is the Hz polarisation, which is etalon's TE. A Meep `mp.Harminv` at the ring's drop port is recorded as a Meep-only diagnostic. The compared ring numbers come from the shared spectral fit in §7.

**Adapter contract for M1/M2.** `bench/etalon/run_device.py` exposes `build(device, tier) -> et.Simulation` and `extract(result) -> PortSpectra`, where PortSpectra holds wavelengths, ports, S_i1, n_eff per port and final decay. The harness owns timing, versions and JSON. The 2D tier needs M1 to ship mode sources and ports in 2D too (a 1D cross-section FDE). plan-m1 does not say so yet (decision D4).

## 7. S-parameters: definition, normalisation, phase

- **Definition:** S_i1(λ) = a_i^out(λ) / a_1^in(λ), where a are modal amplitudes of power-normalised modes. Meep normalises to unit power, and plan-m1 A1(a) does the same.
  - a_1^in is the forward coefficient at port 1's plane, in the same run. The source sits 0.5 µm upstream, and anything it emits backwards goes into the PML, never through port 1.
  - The outgoing coefficient at port i is the one travelling along port i's outward normal. So S11 is the backward wave at port 1.
- **No normalisation run.** The Meep GDS-coupler tutorial does the same. A reference run would double Meep's cost without changing like-for-like-ness.
- **Phase:** e^(−iωt) on both sides, so forward propagation gives S21 ∝ e^(+iβL). Phase is compared only for the straight waveguide.
  - Both of its ports see identical cross-sections, shifted by a whole number of cells. Each code's own mode-phase choice therefore cancels in S21 = a_2/a_1. That holds for MPB's "deterministic" choice and for etalon's A1 convention alike.
  - Pilot P3 checks this on the Meep side: arg S21 must equal 2π·k_dom·L (Meep's k omits 2π) to within the FDTD-vs-MPB dispersion.
  - Elsewhere the port cross-sections differ in orientation (the bend), or the phase depends on n_eff over tens of µm, so only magnitudes are compared there.
- **Wavelengths:** uniform in λ (Lumerical style), passed to Meep as f = 1/λ.
- **One excitation per device.** It gives every quantity in §5.

## 8. Metrics, gates and the report (decision D6)

"|ΔS| < 1 %" needs a precise meaning per device. Proposed:

| Device | Gated metric | Gate |
| --- | --- | --- |
| point2d | max_λ \|T_e − T_m\| | < 1e-3 |
| straight | max_λ \|S21_e − S21_m\| (complex) | < 0.01. This also means \|Δφ\| ≲ 0.01 rad, i.e. Δn_eff < 2.5e-4 over 10 µm, so it really tests M1's subpixel smoothing. |
| bend | max_λ \| \|S21_e\| − \|S21_m\| \| | < 0.01 |
| dc | max_λ \|Δ\|S31\|²\| and \|Δ\|S41\|²\| | < 0.01 (one point of power) |
| mmi | max_λ \|Δ\|S21\|²\| and \|Δ\|S31\|²\| | < 0.01; imbalance in dB reported |
| ring, per resonance in band | \|Δλ_res\| / FSR, \|ΔFSR\| / FSR, \|ΔQ\| / Q, \|Δ min\|S21\|²\| (through-port minimum, linear) | < 0.01 each; extinction is reported in dB |

**Headline number.** Every device also reports **max |ΔS|** = max over the band and all measured entries of | |S_e| − |S_m| |. It gives one comparable number per row, and it is the column the CLAUDE.md "definition of done" refers to.

**Ring metrics** are computed by one function in `metrics.py` from each side's spectrum, so the extraction is identical:
- λ_res and Q come from a Lorentzian fit to each drop-port peak (|S31|²) over ±FSR/4.
- FSR is the spacing between adjacent resonances.
- Extinction is 10 log₁₀ of the off-resonance through-port maximum over its minimum.
- The 1.54–1.56 band holds 2–3 resonances at the expected FSR of 7–9 nm, and 401 points give about 30 samples per FWHM at the expected Q ≈ 900.

**Report.** `bench/results/<sha>.md` gives:
- a header: tier, resolution, PML, S and courant, Meep version and ranks, etalon version, platform
- one row per device: compared quantity, gate, max Δ, pass, max |ΔS|, etalon GPU / etalon CPU / Meep CPU wall time, resolution
- a section per device with the ring resonance table, n_eff per port on both sides (diagnostic: separates mode-solver from propagation differences) and final decay levels

**Meep sanity checks** stop a broken reference from passing quietly:
- straight |S21| ≥ 0.99
- Σ_i |S_i1|² ≤ 1.001
- MMI |S21| ≈ |S31|, which holds by symmetry
- |S11| < 0.05

**Row status.** Unsupported devices show "needs M1 (...)" with Meep's timing only. A device whose decay exceeds 1e-5 on either side is marked "not converged" and is not gated. The same summary goes into the `meep_comparison` section of `results/<sha>.json`.

## 9. Out-file schema (both sides): `bench/<solver>/out/<device>.json`

```json
{
  "schema": "etalon-bench/1",
  "device": "straight", "tier": "2d", "solver": "meep",
  "config_sha256": "…", "code_sha256": "…", "git_sha": "7787804", "date": "2026-10-16T09:00:00Z",
  "wavelengths_um": [1.5, 1.502],
  "ports": [{"name": "1", "center_um": [-5.0, 0.0, 0.0], "size_um": [0.0, 2.5, 0.0], "normal": "-x", "mode": 0}],
  "runs": [{
    "backend": "meep-mpi", "status": "ok", "message": null, "needs": null,
    "versions": {"meep": "1.35.0", "python": "3.12.7", "numpy": "2.3.1"},
    "hardware": {"cpu": "AMD Ryzen 5 5600 6-Core Processor", "processes": 6, "gpu": null, "platform": "Linux-…-WSL2"},
    "precision": "double", "resolution": 50,
    "grid": {"dl_um": 0.02, "cells": [700, 300], "cells_total": 210000, "pml_um": 1.0,
             "courant_meep": 0.5, "courant_fraction": 0.7071, "dt_s": 3.3356e-17, "steps": 29979},
    "run_time_s": 1.0e-12, "wall_time_s": 41.2, "stepping_time_s": 37.9, "extrapolated": false,
    "final_decay": 3.1e-7,
    "s": {"S11": [[0.001, -0.002]], "S21": [[-0.62, 0.78]]},
    "n_eff": {"1": [2.61], "2": [2.61]},
    "extra": {}
  }]
}
```

- **`runs`:** a list, so etalon's file holds a `cuda` and a `numpy` run in the same layout as Meep's single run.
- **Unsupported devices:** `status: "unsupported"`, with `needs` and `message` set and no `s`.
- **Partial runs:** when a NumPy 3D run would take longer than `cpu_full_run_max_minutes`, it steps a fixed number of steps, extrapolates the wall time (`extrapolated: true`, no `s`) and the report prints "est.".
- **`code_sha256`:** hashes the Meep scripts plus the shared modules they import. The harness re-runs Meep only when that hash or `config_sha256` changes, or with `--force-meep`. Meep references are expensive and depend on neither etalon nor its git SHA.

## 10. Tests (no GPU, no Meep)

| ID | Test |
| --- | --- |
| B1 | config: loads; an unknown key fails with its name; extents are an even number of cells; pml × res is an integer; tier device lists exist; courant map; Meep units (1.55 µm → 0.645161, 1 fs → 0.299792 a/c); Meep fwidth reproduces etalon's τ; hash is stable under key reordering and changes when any number changes |
| B2 | geometry: polygons closed and simple; strip width 0.5 along every normal; DC gap 0.236 and ring gap 0.2 measured from the polygons; ports on centrelines with normals along the axis; each port plane inside the region and holding one strip; source upstream of port 1; 2D and 3D share the in-plane polygons |
| B3 | schema: round trip; [re, im] encoding; missing port / wrong length / NaN rejected |
| B4 | metrics: synthetic Lorentzian combs recover λ_res, Q, FSR and ER to 1e-4, also with noise; imbalance and coupling ratio; complex vs magnitude differences |
| B5 | report on mocked Meep and etalon files: every device row; "needs M1"; stale hash refused; mismatched wavelengths refused; gate pass/fail; "not converged"; "est." timing; Meep sanity flags; `<sha>.json` section written |
| B6 | runner: exact command lines for the `native` and `wsl` runners (never executed); Meep cache: missing / fresh / stale |
| B7 | import guard (AST): no `meep` import outside `bench/meep/`; no `etalon` import inside it |
| B8 | etalon adapter: `point2d` builds an `et.Simulation` matching the config (cells, courant 0.7071, PML 50 layers) and runs a reduced copy on NumPy; the five raise `NeedsMilestone` naming M1 and the missing features |
| B9 | record: merging a section keeps the others; the dirty flag ignores `bench/results` and both `out/` dirs |

ruff and mypy stay clean on `bench/` and `tests/bench/`. The Meep script cannot be executed in tests. Its parameter derivation lives in `config.py` and `devices.py`, which B1 and B2 test, and the script itself only maps those values to `mp.*` calls.

## 11. Order of work (small commits)

1. This plan, and the `mvp-spec.md` §5 config path (done in this commit).
2. `bench` package, `config.yaml`, `config.py`, B1. PyYAML goes into a `bench` dependency group, and `THIRD_PARTY.md` is updated (D9).
3. `devices.py`, B2, `plot_devices.py` → `results/bench_devices.png`.
4. `schema.py`, `metrics.py`, `record.py`, `report.py`, B3–B5, B9. `validate_m0.py` writes through `record.py`.
5. `meep/env.yaml`, `meep/run_device.py`, the runner in `run_meep_comparison.py`, B6, B7.
6. `etalon/run_device.py`: point2d, `NeedsMilestone`, B8.
7. **Needs D1 approval (install):** Meep pilot on the 2D tier:
   - **P1** PML 0.5 / 1.0 / 2.0 µm
   - **P2** run times to 1e-5 decay, then frozen
   - **P3** MPB phase determinism
   - **P4** Meep self-convergence at res 50 vs 100, recorded as Meep's own discretisation error
   - **P5** Meep 3D throughput from a short straight-waveguide run

   Then the Meep 2D references, committed; point2d end to end; and the first `results/<sha>.md`.
8. **Needs CPU time OK:** Meep 3D references for straight and bend (hours each) and DC (about half a day), in the background.

## 12. Decisions for review

Say "OK" to take every recommendation.

1. **Where Meep runs.** *Recommended:* WSL2 with Ubuntu 24.04, micromamba (BSD-3) and `bench/meep/env.yaml`. This is the path Meep's docs give for Windows, and the command is the same one a Linux box runs. The runner has two presets: `native` (Linux box) and `wsl` (`wsl.exe -d <distro> --cd <repo> -- micromamba run -n etalon-meep mpirun -np 6 python -m mpi4py -m bench.meep.run_device …`).
   - Footprint: about 4 GB on disk (distro ≈ 1.5 GB, env ≈ 2 GB).
   - May I install these? Nothing is installed yet.
   - The 3D DC run needs more than WSL's default 16 GB. Raising it is a `.wslconfig` setting you would make yourself.
   - *Alternative:* Docker Desktop, which is already installed. It needs no new distro, and an image pinned by digest is very reproducible. It is a third code path, though, and needs the daemon running.
   - *Later:* a Linux box with ≥ 64 GB RAM for the 3D MMI and ring (see 3).
2. **Handling M0:** option B in §3 (adapters gated on M1, plus `point2d` now).
3. **Tiers.** A 2D tier with all five devices plus point2d, using effective index n = 2.84778. A 3D tier with straight, bend and DC on this machine. The 3D MMI and ring are marked "needs ≥ 16 GB GPU / ≥ 64 GB RAM host" until such hardware exists (plan-m1 C3).
   - Also, `mvp-spec.md` M4 measures the ring in a 10 × 10 × 3 µm cell, but an R = 10 µm ring needs about 30 × 25 × 3 µm. Which should change: the M4 cell, or the 3D ring radius?
4. **M1 scope.** M1 should support mode sources and ports in 2D (a 1D cross-section) as well as 3D. Otherwise the 2D tier waits for whichever milestone adds them.
5. **Geometry, matching Liu & Poon where they overlap:**
   - (a) DC per Liu & Poon: gap 0.236 and length 20 instead of §5's 0.2 and 10. Our numbers then sit beside two published solvers, with the caveats of fixed vs Palik index and cosine vs gdsfactory S-bends.
   - (b) Ring: keep §5's add–drop, but with Liu & Poon's racetrack coupler (4 µm straights). This gives Q ≈ 900 and ≈ 10 ps runs. A point-coupled circular ring would have Q ≈ 1e4 or more and need runs over 100 ps.
   - (c) Circular arcs for the bend and ring; Euler later.
   - (d) MMI length 33.6 µm, from self-imaging 3Lπ/8 with the slab index. §5's "≈ 42" does not fit W = 6. No tuning sweep: the comparison does not need the optimum, and symmetry fixes the imbalance.
   - `mvp-spec.md` §5 rows would be updated to match.
6. **The meaning of "|ΔS| < 1 %":** the gate table in §8. In particular:
   - complex S21 for the straight waveguide (strict on phase)
   - power points for the DC and MMI
   - 1 % of FSR, FSR, Q and through-port minimum for the ring
7. **Shared numerics:**
   - resolution 50 px/µm (20 nm, ≈ 22 cells/λ in Si; Liu & Poon needed 20 for the ring)
   - PML 1.0 µm in 2D and 0.5 µm in 3D (pending P1)
   - Meep S = 0.5
   - fixed run times frozen after P2
   - etalon in single precision (Meep's conda build is double)
   - no symmetry planes in either code
8. **Meep data in git.** Commit `bench/meep/out/*.json` as reference data; git-ignore `bench/etalon/out/`. Meep's output is not covered by its GPL.
9. **Config reader.** PyYAML 6.0.3 (MIT, checked on PyPI 2026-10-16) in a new `bench` dependency group, not an etalon runtime dependency. The config is parsed into pydantic models, which the Meep env also has (conda-forge pyyaml and pydantic, both MIT).
   - `THIRD_PARTY.md` gains PyYAML, plus a section for **Meep 1.35.0 (GPL-2.0-or-later): external benchmark, not a dependency, never imported by etalon, run only in `bench/meep/env.yaml`'s environment**, together with that environment's tools (micromamba, mpich, mpi4py).
10. **`results/<sha>.json` collision.** `validate_m0.py` already writes that file. Both scripts would merge their own top-level section (`m0`, `meep_comparison`) through `record.py`. The existing `4b745c7.json` stays as it is.
11. **CPU timing.** The NumPy backend is the single-threaded reference. It runs in full when the estimate is ≤ 30 min, and otherwise as a measured partial run, extrapolated and marked "est.". Meep runs with 6 MPI ranks, one per physical core, and the rank count is recorded.

## 13. Risks

- **Meep API details I have not confirmed in its docs yet:** whether `add_mode_monitor` takes an explicit frequency list (uniform λ), `geometry_center`, and Prism with `height=mp.inf` in 2D. Each is checked against the Python User Interface page when the script is written. The fallback is uniform-frequency sampling, interpolated in the report.
- **Grid alignment.** If Meep's nodes are offset from etalon's by Δ/2, point2d will show it at the 1e-4 level. That is its purpose.
- **WSL file access.** WSL reads the repository through `/mnt/c`, which is slow for many small files but irrelevant for a few JSON files. Outputs are written by rank 0 only (`mp.am_master()`).
- **Meep 3D timings** in §2 are estimates until P5.
- **Tight gates.** The straight-waveguide phase gate and the ring Q gate may prove unreachable even with both codes correct. If so, I stop and report the measured numbers with Meep's own P4 discretisation error. The gate is not moved quietly.
