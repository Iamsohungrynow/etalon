# M0 plan — skeleton + 2D TE FDTD

Status: approved 2026-10-15 (all §8 recommendations accepted) · milestone M0 of `mvp-spec.md`

## 1. What M0 delivers

A 2D TE FDTD (Ex, Ey, Hz) with a NumPy reference backend and a CuPy `RawKernel` backend that agree to 1e-5, CPML on all four faces, a point source with a Gaussian pulse, DFT monitors, and the vacuum validation.

Acceptance (from `mvp-spec.md` §4):

| Criterion | How it is measured | Pass |
| --- | --- | --- |
| Phase velocity within 0.5 % of c after dispersion correction | V1: \|v_measured / v_Yee − 1\| on 0° and 45° (§5) | < 5e-3 (the test enforces 1e-3) |
| CuPy == NumPy | G1–G4: ‖gpu − cpu‖∞ / ‖cpu‖∞ for every field and monitor | ≤ 1e-5 (float32), ≤ 1e-12 (float64) |
| Throughput | G6: 2000 × 2000 cells, cell-updates/s (cells incl. PML × steps / wall time, compile excluded) | ≥ 2e8 on an RTX 3060-class GPU (this machine: RTX 4060 Ti 8 GB); printed, never fails |

Plus a validation plot at `bench/results/m0_vacuum.png`.

Not in M0: 3D, 2D TM, mode solver, subpixel smoothing, nonuniform grid, dispersive media, HDF5 output, Studio.

## 2. Package layout

Created in M0 (✓ = already written for this review):

```
pyproject.toml                  ✓ hatchling; extras: gpu = cupy-cuda12x; dev group: pytest, ruff, mypy
LICENSE                         Apache-2.0 text (step 5)
README.md, THIRD_PARTY.md       step 5
etalon/
  __init__.py                   ✓ public names: Simulation, Medium, Box, PointSource, GaussianPulse,
                                  DFTMonitor, PML, UniformGrid, C_0, wvl_to_freq, freq_to_wvl (+ analysis)
  constants.py                  ✓ C_0 (µm/s), C_0_SI, MU_0, EPSILON_0, ETA_0, UM
  core/                         ✓ Pydantic v2 models, mypy --strict
    base.py                       EtalonModel (frozen, extra="forbid", no NaN/inf), Coordinate, Size, Wavelengths
    medium.py  source.py  monitor.py  boundary.py  grid_spec.py  simulation.py
  geometry/box.py               ✓ Box
  grid/
    yee.py                      YeeGrid2D: cell counts, Δx, Δy, Δt, node coordinates of each component
    materials.py                ε_r on the Ex and Ey nodes from the structures (staircase)
  fdtd/
    capabilities.py             what this build can run; clear errors for 3D / 2D TM
    sources.py                  g(t) and bilinear injection weights
    cpml.py                     1D σ, κ, α profiles → b, c, 1/κ on E and H nodes per axis
    dft.py                      monitor node sets, interpolation weights, phasor tables
    solver.py                   FDTDSolver: build state, step(), run() — backend-agnostic loop
    backends/
      numpy_backend.py          reference update_h_te, update_e_te, accumulate_dft
      cupy_backend.py           compiles and launches the kernels below
      cuda/update_te.cu         update_h_te, update_e_te (CPML fused), REAL = float | double
      cuda/dft.cu               accumulate_dft
  io/result.py                  SimulationResult: result[name][component] → xarray.DataArray
  analysis/dispersion.py        numerical_phase_velocity (Yee relation), measured_phase_velocity
examples/00_vacuum_pulse.py     ✓ the user-facing script this API was designed from
bench/
  validate_m0.py                writes bench/results/m0_vacuum.png + .json
  throughput_m0.py              writes bench/results/m0_throughput.json
tests/
  unit/        fast, CPU      ✓ test_models.py (20 tests)
  gpu/         importorskip("cupy"), marker gpu
  validation/  marker validation, CPU, ~1–3 min total
```

Two rules keep this readable: anything a user can see is in µm and s (models, `YeeGrid2D`, result coordinates); everything below `fdtd/` is SI, with one conversion where the solver builds its state. `core/` never imports `fdtd/`; `Simulation.run()` imports the solver lazily.

## 3. The API (models in `etalon/core/`, already written)

| Model | Fields (defaults) | Notes |
| --- | --- | --- |
| `Simulation` | `center=(0,0,0)`, `size`, `medium=Medium()`, `structures=()`, `grid`, `boundary=PML()`, `sources` (≥ 1), `monitors=()`, `run_time` [s], `courant=0.99`, `precision="single"`, `backend="auto"` | size_z = 0 → 2D. Validates: x/y size > 0, sources and monitors inside the region (2D: in the plane), unique monitor names. |
| `Medium` | `n=1.0`, `name=None` | n ≥ 1 enforced with an explanation; `.permittivity = n²` |
| `Box` | `center=(0,0,0)`, `size`, `medium`, `name=None` | later structures win; 2D inclusion: the plane z = center_z inside the box's z-extent |
| `PointSource` | `center`, `component` (Ex…Hz), `pulse`, `name=None` | bilinear spread over the 4 nearest nodes; J = amplitude·g(t)/(Δx Δy) |
| `GaussianPulse` | `wavelength` [µm], `bandwidth` [µm, full span], `amplitude=1.0` | g(t) = A exp(−(t−t0)²/2τ²) sin(2π f0 (t−t0)); σ_f = (f_hi − f_lo)/2, τ = 1/(2πσ_f), t0 = 5τ; exactly zero-mean |
| `DFTMonitor` | `name`, `center=(0,0,0)`, `size=(0,0,0)`, `wavelengths` (list or array), `components=None` | raw Yee nodes along axes with size > 0; linear interpolation along axes with size = 0 |
| `PML` | `layers=12`, `grading_order=3`, `sigma_scale=1`, `kappa_max=1` | CPML added outside `size`; α fixed at 0 in M0 (kernels carry it) |
| `UniformGrid` | `dl` [µm] | N = ceil(size/dl), Δ = size/N, so edges are exact and Δ ≤ dl |

All models are immutable, reject unknown keywords (a typo is an error, not a silent default), accept NumPy arrays, refuse NaN/inf, and round-trip through JSON with a `type` tag on every model that will join a union later (Box | Cylinder | PolySlab, PointSource | ModeSource, …). Field docstrings land in the JSON schema, so Studio can show them as help text.

Result access, as used in the example: `result["far"]["Hz"]` → complex `xarray.DataArray`, dims `("wavelength",)` for a point monitor and `("x", "y", "wavelength")` for a plane, coordinates in µm on that component's own Yee nodes; `result.grid` → `YeeGrid2D`; `sim.summary()` → cells, Δt, steps and memory before running.

## 4. Numerics

### 4.1 Yee lattice, 2D TE (Taflove & Hagness 3rd ed., ch. 3)

Cells i = 0…Nx−1, j = 0…Ny−1 cover the region plus the PML; node positions relative to the outer corner:

| Component | Position | Array shape |
| --- | --- | --- |
| Hz | ((i+½)Δx, (j+½)Δy) | (Nx, Ny) |
| Ex | ((i+½)Δx, jΔy) | (Nx, Ny+1) |
| Ey | (iΔx, (j+½)Δy) | (Nx+1, Ny) |

Arrays are C-ordered with y fastest. Tangential E on the outer boundary (Ex at j = 0, Ny; Ey at i = 0, Nx) is never updated, i.e. PEC behind the PML.

Updates, with E at integer and H at half-integer time steps:

```
Hz^{n+½} = Hz^{n−½} + (Δt/μ0) [ ∂y Ex − ∂x Ey ]^n − (Δt/μ0) Mz^n
Ex^{n+1} = Ex^n     + (Δt/ε0 ε_r) [ ∂y Hz ]^{n+½}   − (Δt/ε0 ε_r) Jx^{n+½}
Ey^{n+1} = Ey^n     − (Δt/ε0 ε_r) [ ∂x Hz ]^{n+½}   − (Δt/ε0 ε_r) Jy^{n+½}
```

with centred differences, e.g. ∂y Hz at Ex(i, j) = (Hz[i, j] − Hz[i, j−1]) / Δy. Time step: Δt = courant / (c √(1/Δx² + 1/Δy²)) (ch. 4, Courant limit).

### 4.2 CPML (Roden & Gedney 2000; Taflove & Hagness ch. 7)

Each derivative normal to a PML face becomes (1/κ) ∂w F + ψ, with ψ advanced by recursive convolution, ψ ← b ψ + c ∂w F, b = exp(−(σ/κ + α)Δt/ε0), c = σ(b − 1)/(σκ + κ²α). Four auxiliary arrays in 2D TE: ψ_Ex,y, ψ_Ey,x, ψ_Hz,x, ψ_Hz,y. Profiles σ = σ_max ρ^m, κ = 1 + (κ_max − 1)ρ^m, α = α_max(1 − ρ), σ_max = sigma_scale · 0.8(m+1)/(η0 Δ √ε_r), evaluated at each component's own position (integer nodes for E-type derivatives, half nodes for H-type). b, c, 1/κ are stored as 1D arrays per axis; inside the region b = 1, c = 0, 1/κ = 1, so ψ stays exactly 0 and one kernel serves the whole grid. M0 stores ψ as full-size arrays (2000² float32 ≈ 16 MB each); trimming them to the PML slabs is an M4 job.

### 4.3 Source injection

J (or M) of a point source is spread over the 2 × 2 nearest nodes of its component's sub-lattice with bilinear weights (Σw = 1, Σw·x = x_source). Electric currents are sampled at t = (n+½)Δt, magnetic at t = nΔt — the times at which each update consumes them. Weights times g(t) are computed on the host in float64 and cast once, so both backends inject identical numbers.

### 4.4 DFT

For each monitor, component and wavelength: F += field · exp(+iωt_n) Δt, with t_n = (n+1)Δt for E (after the E update) and (n+½)Δt for H. The phasors exp(+iωt_n)Δt are computed on the host in float64 every step and cast to complex64: computing the phase ωt_n ≈ 10³ rad in float32 would cost ~1e-4 rad. Point and line monitors accumulate their raw neighbouring nodes and interpolate once at the end (the DFT is linear, so this equals interpolating every step).

### 4.5 Backends

All array math goes through `xp`. The NumPy backend is the reference: plain slicing, written to read like §4.1–4.2. The CuPy backend compiles `fdtd/backends/cuda/*.cu` with `cupy.RawKernel`, one thread per node, `REAL` defined as `float` or `double` at compile time, and `--fmad=false` so the GPU performs the same IEEE operations in the same order as NumPy. I expect bitwise or near-bitwise agreement; the contract stays 1e-5.

"rtol 1e-5" is applied as a max-norm: ‖gpu − cpu‖∞ ≤ 1e-5 ‖cpu‖∞ per array. An element-wise rtol is meaningless where a field crosses zero.

## 5. Vacuum validation (the method behind V1 and the plot)

The Yee numerical dispersion relation in 2D (the brief cites Taflove & Hagness 3rd ed. eq. 4.17; I implement the relation below and will check the equation number against the book):

```
[ sin(ωΔt/2) / (cΔt) ]² = [ sin(k̃ cosφ Δx/2) / Δx ]² + [ sin(k̃ sinφ Δy/2) / Δy ]²
```

`numerical_phase_velocity` solves it for k̃ by Newton's method from k = ω/c (closed form at φ = 0) and returns ṽp/c = ω/(k̃c). In a medium, c → c/n.

Measurement: an Hz point source on an Hz node; Hz point probes on Hz nodes at two radii along φ = 0° and φ = 45°. Only these symmetry directions are used, because there the ray direction equals the wave-vector direction on an anisotropic lattice. The probe ratio F(r₂)/F(r₁) cancels the source spectrum and the DFT time sampling exactly. k̃ is the root of arg[H0⁽¹⁾(k̃r₂) / H0⁽¹⁾(k̃r₁)] = unwrapped arg[F(r₂)/F(r₁)], which removes the geometric phase of the 2D cylindrical wave (the 1/(8kr) term is ~0.06 % at these radii, so it cannot be ignored). The 2π ambiguity is fixed against k₀(r₂ − r₁).

Runs: Δ = 0.1 µm and 0.05 µm with a band of 0.9–1.8 µm cover 9 to 36 cells per wavelength. At 10 cells per wavelength theory predicts ṽp/c = 0.9913 on axis and 0.9998 on the diagonal at courant 0.99; reproducing that 0.9 % anisotropy is the real test that the scheme is exactly Yee.

Plot `bench/results/m0_vacuum.png`: (a) ṽp/c against cells per wavelength — measured points, theory lines, 0° and 45°; (b) residual v_measured/v_Yee − 1 with the ±0.5 % band; (c) Re Hz at 1.55 µm showing the cylindrical wave and the quiet PML; (d) CPML reflection error against time (V4).

## 6. Test list

**unit** — CPU, seconds, `tests/unit/`

| ID | Test |
| --- | --- |
| U1 | constants: c exact, ε0μ0c² = 1, wvl ↔ freq round trip ✓ |
| U2 | models: example builds, JSON round trip, frozen + hashable, typo → error, NumPy inputs, NaN/inf rejected, n < 1, courant range, band limit, region and plane checks, unique names ✓ |
| U3 | YeeGrid2D: N = ceil(size/dl) with a float-noise guard (0.56/0.01 = 56.00000000000001 → 56, not 57), Δ, PML outside, node coordinates per component, Δt formula, `summary()` numbers |
| U4 | materials: staircase ε_r on Ex and Ey nodes for a Box; 2D inclusion rule; later structure wins; background |
| U5 | pulse: ∑ g Δt ≈ 0; DFT of the sampled g vs the analytic spectrum; g(0) ≈ 3.7e-6 of peak |
| U6 | CPML profiles: interior b = 1, c = 0, 1/κ = 1; grading and staggering at hand-computed nodes; b ∈ (0, 1], c ≤ 0 |
| U7 | injection weights: Σw = 1, centroid = source position, on-node source → one weight; sample times (n+½)Δt for J, nΔt for M |
| U8 | DFT: a pure tone sampled at E times and at H times gives the expected phasor (checks the half step); node selection inside a box incl. edges; a monitor thinner than one cell along a non-zero axis is an error |
| U9 | discrete energy invariant: closed PEC cavity, no PML, float64, 2000 steps — W = ½Σε(Eⁿ)² + ½Σμ H^{n−½}H^{n+½} constant to 1e-12 (the leapfrog's conserved energy; catches any sign or index slip) |
| U10 | mirror symmetry: centred Hz source in a square domain with CPML — Hz exactly symmetric under x → −x and y → −y (float64) |
| U11 | capability errors: 3D → message naming M1; Ez/Hx/Hy in 2D → message naming TE; `backend="cuda"` without CuPy → clear error, no silent fallback |
| U12 | result: dims and coordinates per monitor type; wavelength coordinates exactly as given |

**validation** — CPU, marker `validation`, `tests/validation/`

| ID | Test | Pass |
| --- | --- | --- |
| V1 | vacuum dispersion, 0° and 45°, 9–36 cells/λ: v_measured/v_Yee − 1 | < 1e-3 (acceptance 5e-3) |
| V2 | vacuum, raw ṽp/c at ≥ 20 cells/λ | within 0.5 % of 1 |
| V3 | uniform medium n = 1.5: same as V1 with c/n | < 1e-3 |
| V4 | CPML reflection: 12 layers vs a domain large enough that its own PML cannot be seen in the window; probes 2 cells from the PML and near a corner; max_t \|Hz − Hz_ref\| / max_t \|Hz_ref\| | < 1e-3 (−60 dB) |
| V5 | late-time stability: 30 000 steps; field energy falls below 1e-8 of its peak and never grows over the last half | — |
| V6 | absolute field vs the analytic 2D Green's function, Hz = (ωε0/4) M̂(ω) H0⁽¹⁾(k̃r), at ≥ 25 cells/λ — checks the 1/(ΔxΔy) normalisation, the Δt in the DFT and the e^(−iωt) sign together | within 1 % |

**gpu** — `importorskip("cupy")`, marker `gpu`, `tests/gpu/`

| ID | Test | Pass |
| --- | --- | --- |
| G1 | `update_h_te` kernel vs NumPy, random fields and random CPML profiles, odd sizes (67 × 53) to catch block-edge bugs | 1e-5 / 1e-12 |
| G2 | `update_e_te` likewise, with random ε_r | 1e-5 / 1e-12 |
| G3 | `accumulate_dft` vs NumPy | 1e-5 / 1e-12 |
| G4 | full run, 131 × 97 cells, 600 steps: dielectric Box, off-grid Ey and Hz sources, CPML, point + plane monitors — every field and monitor | 1e-5 / 1e-12; also reports max deviation and whether bitwise |
| G5 | `backend="auto"` picks CUDA when a device is present | — |
| G6 | throughput, 2000 × 2000, 500 steps; NumPy on 500 × 500 for reference; prints and writes JSON | never fails |

## 7. Order of work (each line a small commit once git exists)

1. `grid/` — YeeGrid2D, materials, `summary()` · U3 U4
2. `fdtd/sources.py`, `cpml.py`, `dft.py` · U5 U6 U7 U8
3. NumPy backend, solver loop, result object, capability checks · U9–U12, example runs end to end
4. `analysis/dispersion.py` · V1–V6
5. CUDA kernels + CuPy backend · G1–G5
6. throughput · G6, `bench/throughput_m0.py`
7. `bench/validate_m0.py` → `bench/results/m0_vacuum.png`
8. pytest, ruff, mypy (strict on `core/`) all clean
9. `THIRD_PARTY.md`, `LICENSE`, README status
10. `docs/plan-m1.md` with open questions — M1 itself does not start

## 8. Decisions for review

Each has a recommendation already built into the models; say "OK" to take them all.

1. **2D TE = (Ex, Ey, Hz).** Taflove's TE_z and Lumerical's 2D TE agree on this.
2. **`courant` is the fraction of the stability limit** (Lumerical's "dt stability factor"), default 0.99. Mirroring Meep's S in the bench harness: courant = S·√D (S = 0.5 → 0.707 in 2D, 0.866 in 3D).
3. **PML outside `size`**, as in Lumerical and Tidy3D. The Meep harness has to add the PML thickness to its cell.
4. **Pulse as its own object**, `pulse=et.GaussianPulse(...)`. `mvp-spec.md` §2 gives `ModeSource` inline `wavelength=, bandwidth=`; I recommend changing §2 to `pulse=` so there is one way to set a source's time signature.
5. **`UniformGrid(dl)`** rather than `Grid`, so `AutoGrid(min_steps_per_wvl=…)` from §2 can join it in M3 without a rename.
6. **`bandwidth` puts the band edges at 1 σ_f** (spectral amplitude ≈ 0.61 of peak).
7. **Sources and monitors outside the region are errors.** Lumerical clips monitors silently; an explicit error seemed safer for M0.
8. **Time convention e^(−iωt)**: DFT kernel e^(+iωt), so phase grows along the propagation direction. The S-parameter phase sign relative to Lumerical gets pinned in M1.
9. **Equality as a max-norm**, and V4's −60 dB PML threshold.

Environment, needed before step 3:

10. **Tooling.** `uv` is not installed (CLAUDE.md mandates it); CuPy, xarray and mypy are missing. Proposal: install uv, create `.venv`, `uv sync` with the `gpu` extra. There is no CUDA toolkit on this machine (driver 591.86 only), so CuPy's NVRTC comes from NVIDIA's pip runtime wheels. I'll confirm the exact package names when installing.
11. **Git.** The folder is not a repository, but CLAUDE.md wants small commits and `bench/results/<git-sha>.json`. Proposal: `git init` and commit this scaffold as the first commit.
12. **Spec location.** CLAUDE.md points to `docs/mvp-spec.md` and `docs/ui-ux-spec.md`; both sit at the repo root. Proposal: move them into `docs/`.

## 9. Risks

- **2D wake.** A 2D Green's function has a tail behind the wavefront. Truncating the DFT early biases the phase. V1 re-runs with doubled `run_time` and requires the result to change by < 1e-4.
- **Citations.** I can't check section and equation numbers in Taflove & Hagness from here. Docstrings cite chapters until each number is verified against the book; Schneider's text is free online and gets checked directly.
- **Windows + CuPy.** NVRTC discovery without a toolkit install is the most likely friction point. The NumPy path does not depend on it.
