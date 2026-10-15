# M1 plan — open questions (draft, not started)

Status: questions for review · 2026-10-16 · milestone M1 of `mvp-spec.md`

**Deliverable:** 3D FDTD, PolySlab + subpixel smoothing, FDE mode solver, mode source, mode port monitor, S-parameters.
**Accepted when:** for a 500 × 220 nm strip, n_eff at 1550 nm is within 0.5 % of the published value; FDTD propagation phase matches the FDE n_eff within 0.5 %; straight-waveguide |S21| ≥ 0.995.

M0 gives M1 a validated base. Its 2D TE update is bit-identical between NumPy and CUDA, within 3.5e-5 of the Yee dispersion relation, and its CPML reaches −91 dB. Its conventions (§8 of `plan-m0.md`) carry over unchanged: e^(−iωt), PML outside `size`, courant as a fraction of the limit, and J/M injected at (n+½)Δt / nΔt.

The full M1 plan with its test list follows once these are answered. Each question lists options with my recommendation first.

## A. Physics conventions — ambiguous, need your call

**A1. Mode normalisation and phase.** S-parameters inherit this convention.
- (a) *Recommended:* power-normalise each mode, ½ Re ∫ (E × H*) · n̂ dA = 1 W (Snyder & Love ch. 11). Fix the phase so that the dominant transverse E component is real and positive at its |max|.
- (b) Normalise to unit field amplitude (|E|max = 1). Simpler, but then |S|² is not power.

**A2. Modal amplitudes for S-parameters.**
- (a) *Recommended:* the bidirectional overlap a± = ¼ ∫ (E × H_m* ± E_m* × H) · n̂ dA, which separates forward and backward waves on one plane. The amplitudes get normalised by the source run's incident amplitude, so S = a_out / a_in at the monitor planes.
- (b) Forward-only overlap with a separate reflection monitor. Simpler, but it mixes in backward power.

**A3. S-parameter phase reference.** With e^(−iωt), forward propagation gives phase +βL. Lumerical users compare phases directly, and I can't verify from here which sign their exported S-matrices use.
- (a) *Recommended:* keep physics e^(−iωt) internally, and add a `phase_convention="physics" | "engineering"` switch on Touchstone export (M3). The default needs your decision after a check against one Lumerical .sNp file you trust.
- (b) Use engineering e^(+jωt) everywhere in the API. This differs from Meep, the benchmark.

**A4. Subpixel smoothing.**
- (a) *Recommended:* the full anisotropic effective-permittivity tensor (Farjadpour et al. 2006). It keeps second-order convergence on curved and oblique walls, i.e. the ring and the bend, and Meep uses it too, so the 1 % comparison stays like-for-like. The cost: the update reads the off-diagonal ε⁻¹ terms, so each E component needs the other two averaged to its node. That means more kernel work and memory, but only in cells cut by an interface.
- (b) Diagonal-only (projected) smoothing. Simple and diagonal, and exact enough for the axis-aligned straight waveguide. It degrades on oblique walls, so the bend and ring would likely miss 1 %.
- (c) Staged: (b) in M1 for the straight-waveguide acceptance, (a) before M2.

**A5. Mode solver discretisation (Fallahkhair, Li & Murphy 2008).**
- (a) *Recommended:* solve on exactly the FDTD's Yee cross-section, with the same staggering and the same smoothed ε. The injected mode is then an eigenmode of the discrete FDTD grid, which keeps back-reflection from the source small and gives the "FDTD phase matches FDE n_eff to 0.5 %" check a fair basis.
- (b) A separate, finer mode-solver mesh interpolated onto the FDTD plane. More accurate n_eff in isolation, but it injects a slightly mismatched mode.
- Mode-solver boundary: PEC with enough cladding (recommended for M1), with PML in the mode solver later for leaky modes.

**A6. Mode source injection.**
- (a) *Recommended:* the equivalence principle on one plane, J = n̂ × H_m and M = −n̂ × E_m, with E and H at their own Yee positions and half-step times, driven by the GaussianPulse. This is unidirectional to the degree that the discrete mode matches (A5). `mvp-spec.md` §9 also leans this way.
- (b) A soft source plus a back-reflection monitor to subtract.

**A7. Flux and overlap on the staggered grid.** E and H live at different nodes and times. M0's DFT already uses each field's exact time, so the time stagger is handled.
- (a) *Recommended:* interpolate H to the E nodes of the monitor plane (average the 2 or 4 neighbours) before forming E × H*.
- (b) Average both fields to cell centres. This is symmetric, but adds an O(Δ²) error to both.

## B. Reference data — you choose

**B1. Published n_eff for the 500 × 220 nm strip at 1550 nm** (open question in `mvp-spec.md` §9). Which source and value do we pin? Candidate: Chrostowski & Hochberg, *Silicon Photonics Design*. The material indices also need fixing: Si 3.476 and SiO₂ 1.444, fixed and non-dispersive as in the spec example? A 0.5 % test is only as good as the reference.

## C. Engineering decisions with a recommendation

**C1. CPML memory in 3D.** M0 keeps ψ arrays at full grid size, which is fine in 2D. In 3D, twelve full-size ψ arrays add 48 B/cell. For the spec's 7.5e7-cell case that is 3.6 GB of mostly zeros. *Recommended:* store ψ only in the PML slabs from M1, instead of waiting for M4 as planned.

**C2. CFS α in the PML** (deferred from M0). Waveguides that enter the PML carry evanescent tails, where α > 0 helps. *Recommended:* expose `alpha_max` as a dimensionless multiple of ε0·ω0 (ω0 from the source centre), default 0.1 or set by testing a waveguide into the PML. Units are the open part.

**C3. Dev GPU memory.** This machine has an RTX 4060 Ti with 8 GB. At 20 nm, the MMI (≈ 45 × 8 × 3 µm, 1.4e8 cells ≈ 5.4 GB plus monitors) is close to that limit, and the ring is too. M1 itself fits, but M2 and M4 will need a 16–24 GB card or coarser meshes. Is a larger card available?

**C4. 2D TM.** It is cheap to add while generalising to 3D, since TM is the mirror of TE. *Recommended:* include it in M1, so every 2D simulation works whatever its source component.

**C5. CI and platform.** `mvp-spec.md` says Linux first, but development so far is on Windows; M0 passes there. *Recommended:* add a Linux CI job for CPU tests wherever the repository will live. Where will that be?
