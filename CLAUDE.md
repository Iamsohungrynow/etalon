# etalon — project brief for Claude Code

## What this is

**etalon** is an open-core, GPU-accelerated, **on-premise** photonic device simulation platform: 3D FDTD + eigenmode (FDE) solver + a Python-native API. Built in Singapore for photonics design teams in China, Singapore and the US.

Why it exists: the industry standard (Ansys Lumerical FDTD/MODE) is US-owned (Synopsys) and was cut off from China once in 2025; the only modern GPU competitor (Tidy3D by Flexcompute) is US-owned and cloud-only. Our wedge is **non-US origin + runs on a single local GPU + Python-native + seat pricing**. The moat is solver speed and correctness, nothing else — so correctness and performance are the whole product.

Name: a Fabry–Pérot *etalon*; *étalon* is French for "standard".

## MVP goal (what we are building now)

A Python package `etalon` that simulates standard passive silicon-photonic components in 2D and 3D FDTD on **one NVIDIA GPU**, with an identical-result **CPU fallback**, and reproduces Meep/Lumerical S-parameters within **1 %** on five reference devices:

1. straight strip waveguide (transmission ≈ 1)
2. 90° bend (Euler or circular)
3. directional coupler
4. 1×2 MMI
5. add–drop ring resonator

Definition of done = `bench/run_meep_comparison.py` prints an S-parameter accuracy + timing table for all five, with |ΔS| < 1 % vs Meep.

The MVP also ships **etalon Studio**, a local web UI (`etalon studio` → `http://127.0.0.1:8787`) for preview + cost estimate, run monitoring, and results viewing/export. The Python script stays the source of truth; Studio never rewrites user code. Full spec: `docs/ui-ux-spec.md`.

## Non-goals for the MVP

Geometry editing / CAD or a script editor inside Studio · inverse design / adjoint · multi-GPU · dispersive-material fitting beyond fixed index + one Lorentz pole · active devices (thermo/electro-optic) · foundry PDK libraries · licensing/auth · cloud · non-NVIDIA backends (keep the kernel layer swappable, but do not build them).

## Architecture

```
etalon/
  core/        Pydantic v2 models: Simulation, Structure, Medium, Source, Monitor, Boundary
  geometry/    Box, Cylinder, PolySlab; GDS import via gdstk (and gdsfactory later)
  grid/        Yee grid, uniform + nonuniform mesh, subpixel smoothing (effective permittivity tensor)
  fdtd/        time stepping; backends/{numpy,cupy}; CPML; sources (point, Gaussian beam, TFSF, mode); DFT monitors
  mode/        vector finite-difference eigenmode solver (scipy.sparse.linalg.eigs); mode overlap
  analysis/    S-parameters, flux, field plots
  io/          HDF5 results (h5py), xarray wrappers, Touchstone export
  studio/      FastAPI server (server.py, jobs.py, preview.py) + static/ (built SPA, copied at wheel build)
studio/        Studio frontend source: React 19 + TypeScript + Vite + Tailwind v4 + Radix + react-three-fiber + ECharts
bench/         Meep comparison scripts — Meep runs in its OWN conda env via subprocess; never imported
docs/          mkdocs-material
examples/      notebooks, one per reference device
tests/
```

**Studio rules:** binds to 127.0.0.1 only; no analytics, no runtime font or asset fetches (everything bundled); field arrays travel as binary float32, never JSON; API client types are generated from the FastAPI OpenAPI schema (`openapi-typescript`), never hand-written; every UI string goes through i18next with `en` and `zh-CN` keys; dark theme is the default. Design tokens, components, screens and the endpoint contract are in `docs/ui-ux-spec.md` — follow it, do not invent screens.

**Backend rule:** all array math goes through `xp` (`numpy` or `cupy`). Hot loops (E/H updates, CPML, DFT accumulation) are CUDA C strings compiled with `cupy.RawKernel`, kept in `fdtd/backends/cuda/*.cu`. Every kernel has a NumPy reference implementation and a test asserting bitwise-close equality (rtol 1e-5) on a small grid.

**Precision:** float32 fields, complex64 DFT accumulators by default; float64 switchable via `Simulation(precision="double")`.

**Units:** API in micrometres and wavelengths in µm (same convention as Tidy3D/Lumerical users expect); internals SI. Frequency in Hz. Provide `et.C_0`, `et.wvl_to_freq`.

**Coordinates:** x, y, z right-handed; a 2D simulation is the z-invariant slice (size_z = 0).

## Tech stack

Python ≥ 3.11 · `uv` for env/packaging · numpy · scipy · `cupy-cuda12x` as optional extra `etalon[gpu]` · pydantic v2 · xarray · h5py · gdstk · matplotlib · fastapi + uvicorn (Studio server) · pytest · ruff · mypy (strict on `core/`) · mkdocs-material.

Frontend (`studio/`): pnpm · React 19 · TypeScript strict · Vite · Tailwind v4 · Radix UI primitives · react-three-fiber + drei · Apache ECharts · zustand · TanStack Query · react-router · i18next · vitest · Playwright. Fonts: Inter + JetBrains Mono, bundled. Icons: Lucide.

## Physics references — implement FROM THESE, not from other codes

- Taflove & Hagness, *Computational Electrodynamics*, 3rd ed. — Yee scheme, Courant stability, DFT monitors, TFSF
- J. B. Schneider, *Understanding the FDTD Method* (free, eecs.wsu.edu/~schneidj) — practical implementation
- Roden & Gedney, 2000 — convolutional PML (CPML)
- Farjadpour et al., *Opt. Lett.* 31, 2972 (2006) — subpixel smoothing
- Fallahkhair, Li & Murphy, *J. Lightwave Technol.* 26, 1423 (2008) — vector finite-difference mode solver
- Snyder & Love, *Optical Waveguide Theory* — mode normalisation, overlap integrals
- Oskooi et al., *Comput. Phys. Commun.* 181, 687 (2010) — Meep paper: architecture ideas only
- Liu & Poon, arXiv:2506.16665 (2025) — the Lumerical-vs-Tidy3D benchmark devices we reproduce

## Licensing and clean-room rules — non-negotiable

- This code is **Apache-2.0**. Never copy, vendor, or import GPL code (**Meep is GPL-2.0**) or LGPL code (the Tidy3D Python client). Meep is an external benchmark only, run by subprocess in a separate environment.
- Do not open Lumerical, Tidy3D or Meep source to implement anything. API *style* may resemble theirs (ideas); code may not.
- Dependencies must be MIT / BSD / Apache / PSF licensed. Run a license check before adding one; record every dependency and its license in `THIRD_PARTY.md`.
- This repository never contains code, data or scripts from NTU, CQT or IQM projects. The founder's PhD work is unrelated and stays unrelated.
- No telemetry, no phone-home, no cloud calls. The product's promise is "your data never leaves your machine".

## Engineering conventions

- Every physics feature ships as: (1) NumPy reference → (2) CuPy kernel → (3) equality test → (4) validation against an analytic case or Meep.
- Tests run without a GPU; CuPy tests `pytest.importorskip("cupy")`.
- Validation ladder before touching real devices: vacuum plane-wave propagation (phase velocity, numerical dispersion) → 1D dielectric slab reflection vs Fresnel → 2D waveguide mode propagation vs mode solver n_eff.
- Keep commits small; every benchmark run writes `bench/results/<git-sha>.json`.
- Prefer boring code: no metaclasses, no clever decorators, no premature abstraction. Readability for physicists > cleverness.
- Docstrings carry the equation and the reference section number.
- Frontend: one component per file, props typed, no `any`; every screen has an empty, loading, and error state; every async call goes through TanStack Query; Playwright smoke test per route against the recorded sample result in `studio/e2e/fixtures/`.
- Solver work and Studio work happen in separate sessions; a Studio session may read `etalon/core/` models but does not change solver code, and vice versa (the API contract in `docs/ui-ux-spec.md` §9 is the boundary).

## Definition of done per milestone

See `docs/mvp-spec.md`. Nothing is "done" without its test and its validation plot.

## Business context for judgement calls

Customers are photonics designers who use Lumerical today. They will try etalon only if (a) their scripts port in a day and (b) results match to the percent. So: API familiarity and correctness beat features; single-GPU memory footprint beats peak throughput; a clear error message beats a silent wrong answer. When in doubt, choose the option a Lumerical user would find least surprising.
