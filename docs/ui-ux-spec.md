# etalon Studio — UI/UX and frontend specification

Status: draft v0.1 · 2026-10-15 · owner: Martina · companion to `mvp-spec.md`

## 1. What Studio is, in one paragraph

**etalon Studio** is the local web app that ships inside the `etalon` Python package (`etalon studio` opens `http://localhost:8787`). It is not a CAD tool and it does not replace the Python script: **the script is the source of truth**, Studio lets you *see* what the script describes before you burn GPU time, *watch* the run, and *read* the results without writing matplotlib code. Everything Studio shows is also reachable from Python; nothing in Studio writes to your script without an explicit action.

Three jobs, in order of how often a user does them:

1. **Check before running** — "Is my geometry right, is the mesh fine enough, how long will this take, how much memory?" (today: people discover a wrong layer after a 40-minute run)
2. **Watch the run** — progress, energy decay, a live low-res field, cancel.
3. **Read and share results** — S-parameter spectra, field slices, mode profiles; export to CSV/Touchstone/PNG; compare two runs.

## 2. Users

| Persona | Context | What they need from Studio |
| --- | --- | --- |
| Device designer (primary) | Writes Python, runs 5–50 sims/day, Lumerical or Tidy3D background, often in China with no cloud access | Preview + cost estimate before run; fast results viewer; export that drops into their report |
| Design lead / reviewer | Does not write the script; opens a colleague's result | Open a results file, understand it in 30 s, compare against a previous run |
| PDK / foundry engineer | Checks solver settings line by line | Every numeric setting visible (grid, PML, run time, Courant); reproducibility info (git sha, version, backend, GPU) on every result |
| Student / evaluator | Installs from docs, has a laptop GPU or none | Templates for the five reference devices; CPU fallback still works; Chinese UI available |

Studio ships bilingual from day one: **English and 简体中文**, switchable in Settings; all strings go through i18n.

## 3. Principles

1. **Script is truth.** Studio reads `.py` (and the JSON spec it produces); it never rewrites user code. Parameter edits apply only to values the script declares with `et.param(...)`.
2. **Show the cost before the run.** Cells, memory, steps, estimated wall-clock, and warnings (mesh too coarse in the highest-index medium, PML thinner than λ/2, monitor outside PML) are on the Setup screen, always.
3. **Numbers with units, everywhere.** µm / nm / THz / dB are printed, never implied. Precision of the number matches what the solver resolved.
4. **Dense but calm.** It is a lab instrument, not a marketing dashboard: one accent colour, no cards-in-cards, monospace for numerics, 13 px body, keyboard first.
5. **Nothing leaves the machine.** No analytics, no update checks without consent, no external fonts at runtime (fonts bundled). The Settings page states this.
6. **Reproducible by default.** Every result carries etalon version, git sha of the user script, backend, GPU model, grid and PML settings; the Results header shows them and the export includes them.

## 4. Information architecture

```
Studio
├── Workspace               list of simulations in the workspace folder
│   └── Simulation /<id>
│       ├── Setup           structure tree · viewport · inspector · cost estimate
│       ├── Run             progress · energy decay · live field · log
│       └── Results         S-parameters · fields · modes · export · compare
├── Mode Solver             cross-section → n_eff, profiles, dispersion sweep
├── Validation              the Meep/analytic benchmark report for this install
└── Settings                backend/GPU · workspace folder · language · theme · privacy
```

Routing: `/`, `/sim/:id/setup`, `/sim/:id/run`, `/sim/:id/results`, `/modes`, `/validation`, `/settings`. Deep links are stable so a result can be pasted in a chat.

## 5. Screens

### 5.1 Workspace (`/`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ etalon Studio        Workspace  Mode Solver  Validation  Settings    │
│ ~/photonics/ring-designs                                [New ▾] [⌕] │
├──────────────────────────────────────────────────────────────────────┤
│  Name                 Status     Last run      Backend   Cells  Time │
│  ring_r10_g200.py     ● done     14:02 today   cuda:0    42 M   3m12 │
│  ring_r10_g180.py     ◐ running  —  step 11 k/26 k       42 M   ~2m  │
│  mmi_1x2_sweep.py     ○ draft    —             —         —      —    │
│  dc_gap200.py         ✕ failed   yesterday     cuda:0    —      —    │
├──────────────────────────────────────────────────────────────────────┤
│  [New from template ▾]  straight wg · bend · DC · MMI 1×2 · ring     │
└──────────────────────────────────────────────────────────────────────┘
```

- A row = one `.py` in the workspace folder (recursive, ignoring `_*`). Status comes from the sidecar `.etalon/` results folder.
- Row click → Setup. Running row click → Run. Done row click → Results.
- "New from template" copies one of the five reference scripts into the workspace and opens Setup.
- Empty state: a short explanation + the template picker; no illustration.
- No-GPU state: a one-line banner "No CUDA device found — runs use the CPU backend" with a link to Settings; never blocks.

### 5.2 Setup (`/sim/:id/setup`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ ring_r10_g200.py                    [Open in editor] [Run ▶]         │
├────────────┬──────────────────────────────────────┬──────────────────┤
│ Structure  │                                      │ Inspector        │
│ ▾ Media    │        3D viewport                   │ ring (PolySlab)  │
│   si 3.476 │   (orbit · XY/XZ/YZ slice · grid)    │ medium   si      │
│   sio2     │                                      │ slab   ±0.110 µm │
│ ▾ Structures                                      │ vertices  64     │
│   bus_wg   │                                      │ ─────────────    │
│   ring  ◀  │                                      │ Parameters       │
│ ▾ Sources  │                                      │ radius  10.0 µm  │
│   in (mode)│                                      │ gap     0.200 µm │
│ ▾ Monitors │                                      │ [Apply & reload] │
│   thru drop│                                      │                  │
│ ▾ Boundary │                                      │                  │
│   PML 12   │                                      │                  │
│ ▾ Grid     │  [XY ▾]  z = 0.000 µm  ───●───       │                  │
├────────────┴──────────────────────────────────────┴──────────────────┤
│ Estimate   42.3 M cells · 3.1 GB · 26 400 steps · ~3 min on RTX 4090 │
│ ⚠ Mesh: 14 steps/λ in si at 1.50 µm (min 20) · ⚠ Monitor "drop" overlaps PML │
└──────────────────────────────────────────────────────────────────────┘
```

- **Structure tree** (left, 240 px): every object the script declared, grouped; selecting highlights it in the viewport and fills the Inspector. Hidden/shown toggles per object (view-only).
- **Viewport** (centre): react-three-fiber. Structures as extruded meshes coloured by medium; sources as translucent planes with an arrow; monitors as wireframe boxes; PML as a hatched shell; grid lines on the current slice plane (toggle). Slice mode shows the permittivity map of that plane, so sub-pixel smoothing is *visible*. Orbit/pan/zoom with standard controls; `1/2/3` switch XY/XZ/YZ; `[`/`]` move the slice; `G` toggles grid; `F` frames selection.
- **Inspector** (right, 280 px): properties of the selected object, read-only, with units. The **Parameters** block lists values the script exposed via `et.param("radius", 10.0, unit="um")`; editing one and pressing *Apply & reload* re-executes the script with overrides (the overrides are stored in the sidecar, the `.py` is untouched).
- **Estimate bar** (bottom, always visible): cells, memory, steps, time estimate (from a calibration run on this machine; shows "unknown" until one exists), plus warnings. The *Run* button is disabled only on errors, never on warnings.
- Loading state: the script is executed in a subprocess to build the spec; show a skeleton with "Building simulation…" and the stdout tail; on exception show the traceback inline with the failing line number.

### 5.3 Run (`/sim/:id/run`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ ring_r10_g200.py  · cuda:0 RTX 4090 · started 14:02        [Cancel] │
├──────────────────────────────────────────────────────────────────────┤
│ ████████████████████░░░░░░░░░  step 18 420 / 26 400 · 2:04 elapsed · ~0:55 left │
├──────────────────────────────┬───────────────────────────────────────┤
│ Field energy (log)           │ Live |E|  z = 0  (every 500 steps)    │
│  ╲                           │                                       │
│   ╲_____                     │   [low-res heatmap]                   │
│         ╲____  threshold 1e-5│                                       │
├──────────────────────────────┴───────────────────────────────────────┤
│ Log                                                                   │
│ 14:02:03  grid 420×420×240, dt 3.84e-17 s, CPML 12 layers            │
│ 14:02:04  mode source: n_eff 2.4471 at 1.550 µm (TE0)                │
│ 14:03:11  step 15000  energy 2.1e-4  3.2e8 cells/s                   │
└──────────────────────────────────────────────────────────────────────┘
```

- Progress over WebSocket, ≤ 4 updates/s. Energy-decay chart has the shutoff threshold drawn, so the user sees *why* a run ends early.
- Live field snapshot is optional (off by default on CPU); downsampled to ≤ 256² per frame.
- Cancel asks for confirmation only if > 1 min has elapsed; a cancelled run keeps partial DFT results and is marked "cancelled".
- Failure: the error, the traceback, and a one-line suggestion when we can match it (out of memory → "reduce grid or use float32"; NaN → "Courant too high or source inside PML").

### 5.4 Results (`/sim/:id/results`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ ring_r10_g200.py · done 14:05 · etalon 0.1.0 · cuda:0 · sha 3f2a9c   │
│ [S-parameters] [Fields] [Modes]                 [Compare ▾] [Export ▾] │
├──────────────────────────────────────────────────────────────────────┤
│  |S|²  ○ dB  ○ phase       ports: in → ☑ thru ☑ drop                  │
│                                                                       │
│   ╭──╮      ╭──╮      ╭──╮          thru                              │
│  ─╯  ╰──────╯  ╰──────╯  ╰───                                         │
│      ╱╲        ╱╲        ╱╲         drop                              │
│  ────  ────────  ────────  ──                                         │
│   1.540      1.545      1.550      1.555  λ (µm)                      │
│  hover: λ 1.5482 µm · thru 0.031 · drop 0.942 · Q ≈ 8 400             │
└──────────────────────────────────────────────────────────────────────┘
```

**S-parameters tab**: ECharts line chart; port pairs as toggles; |S|², dB, phase (unwrapped) views; crosshair readout; resonance markers with FSR/Q computed when the trace has peaks; data table toggle; export CSV / Touchstone / PNG.

**Fields tab**: monitor picker → component (Ex…Hz, |E|, |H|, Poynting S) → plane and slice slider → colormap (viridis for magnitude, RdBu diverging for signed, both colour-blind safe) → linear/log → geometry outline overlay → wavelength picker for DFT monitors. Rendered client-side on a canvas from float32 arrays streamed in binary; pan/zoom; click gives value and coordinates; PNG export at 2×.

**Modes tab**: for mode monitors/sources: n_eff, n_g, polarisation fraction per mode; profile thumbnails; click → full profile with the same field viewer.

**Compare**: pick another finished run in the workspace → spectra overlaid (dashed for the second run), a delta trace, and a settings diff (grid, PML, run time, parameters) so the user sees what changed.

**Export menu**: CSV (spectra), Touchstone `.sNp`, PNG (current view), "Copy Python" (a snippet that loads this result file), path to the HDF5.

Stale state: if the script changed after the run, a yellow bar says "Results are from an earlier version of this script" with a *Run again* button.

### 5.5 Mode Solver (`/modes`)

A standalone page for the most common quick question ("what is n_eff of this waveguide"): cross-section built from a selected simulation at a chosen plane, or from a tiny form (width, height, materials, cladding), wavelength, number of modes → table of n_eff / n_g / TE fraction + profile viewer; wavelength sweep → n_eff and n_g curves. Results exportable as CSV. This page is also where mode sources are debugged.

### 5.6 Validation (`/validation`)

Renders `bench/results/<latest>.md` + JSON: per-device max |ΔS| vs Meep, timing, resolution; a green/amber/red per device. It exists so a sceptical evaluator can see the numbers on their own machine. Button: *Run validation suite* (CPU-only subset by default, ~10 min).

### 5.7 Settings (`/settings`)

Backend (auto / cuda:N / cpu) with detected devices and memory; workspace folder; language (English / 简体中文); theme (dark default / light / system); units display (µm or nm); live-field snapshots on/off; privacy statement ("Studio makes no network requests; fonts and assets are bundled"); version and update check (manual button only).

## 6. Interaction details and states

- Keyboard: `⌘K` command palette (open sim, run, switch tab, toggle slice); `R` run from Setup; `1/2/3` planes; `[`/`]` slice; `⌘E` export; `?` shortcuts sheet.
- Selection sync: tree ↔ viewport ↔ inspector share one selection store.
- Numbers: monospace, SI prefixes, 4 significant figures by default, full precision on hover/copy.
- Long lists (e.g. 64 monitors) virtualised.
- Every async state has: skeleton → content → error-with-retry. No spinners without text.
- Toasts only for completed background actions (export saved, run finished while on another page). Never for errors — errors stay inline where they happened.
- Undo: parameter edits are reversible (history per simulation); nothing else needs undo because Studio does not mutate user files.

## 7. Design system

**Tone**: instrument, not SaaS. Think oscilloscope UI redrawn by a careful typographer.

Dark is the default. Light is the "paper" palette of the visual reference (`docs/design/studio-reference.html`); System follows the OS. Decided 2026-10-16 in `docs/plan-u0.md` §2 and §8 (D12); every text colour reaches WCAG AA (4.5:1) on bg, surface and raised, and every control outline 3:1.

| Token | Dark (default) | Light (paper) |
| --- | --- | --- |
| bg / surface / raised | #0E1013 / #15181D / #1C2027 | #F2F0E4 / #FFFFFF / #E8E6D9 |
| hover | #1C2027 | #E4E2D6 |
| rule (panel and section rules) / rule-subtle (table rows) | #3A414C / #2A2F38 | #000000 / #C9C7BA |
| control (input and button outlines) | #6B7380 | #000000 |
| text / secondary / muted | #ECEEF2 / #A6ADBA / #858D9A | #000000 / #444444 / #666666 |
| accent (one) | #E8B34A (etalon amber — a cavity resonance) | #B8862B, as a fill only |
| accent-ink (accent-coloured text, focus ring) / on-accent | #E8B34A / #0E1013 | #7A5A12 / #000000 |
| ok / warn / error | #4CC38A / #E8B34A / #EC5D62 | #166B3C / #7E5C14 / #B3261E |
| spectrum | `#ff0000 → #ff7f00 → #ffff00 → #00ff00 → #0000ff → #4b0082 → #8f00ff`, a static 2 px stripe under the header only; never behind text or data | same |
| field colormaps | viridis (magnitude), RdBu (signed), both from matplotlib definitions | same |
| categorical (spectra) | Okabe–Ito 8-colour palette | same |

Accent and warn share one hex; status is always a glyph plus a word, so colour is never the only signal.

- Type: **Inter** for UI (13 px body, 12 px dense tables, 15/18/22 px headings at weight 600), **JetBrains Mono** for all numerics and the log. Panel labels and table headers are uppercase JetBrains Mono micro-labels (10–11 px, 0.08em tracking, muted). Both fonts bundled (OFL-1.1, licence texts shipped alongside), no runtime font fetch; CJK fallback to system fonts (`PingFang SC`, `Microsoft YaHei`, `Noto Sans CJK SC`).
- Spacing scale 4 px; square corners (radius 0) on controls and panels; 1 px rules, no shadows except the command palette.
- Chrome: a 40 px header with navigation, the spectrum stripe, and a static 24 px status strip at the bottom with real values only (backend and device, workspace, simulation count, etalon version, offline). Nothing in the chrome animates.
- Cursor: crosshair only over canvases and the viewport; default cursors everywhere else.
- Icons: Lucide (ISC licence), 16 px.
- Density: one density only (compact). No "comfortable" mode in MVP.
- Motion: 120 ms ease-out on panels; none on charts except crosshair.
- Accessibility: WCAG AA contrast on all text; focus rings visible; every colour encoding doubled by a label or line style; charts have a data-table toggle; viewport has a "2D only" mode for users who cannot use orbit controls.

Components (Radix primitives + Tailwind, own styling, no third-party theme): Button, IconButton, Toggle, Segmented, Select, NumberField (unit-aware), Slider, Tree, Table (virtualised), Tabs, Inspector (key–value list), Banner, Toast, CommandPalette, Chart (ECharts wrapper), FieldCanvas, Viewport3D, ProgressBar, LogView, EmptyState, ErrorPanel.

## 8. Frontend architecture

```
studio/                      pnpm workspace, TypeScript strict
  src/
    app/                     routes (react-router), layout, command palette
    features/
      workspace/  setup/  run/  results/  modes/  validation/  settings/
    components/              design-system components (above)
    viewport/                react-three-fiber scene: meshes, slice plane, grid, gizmos
    charts/                  ECharts configs: spectra, energy decay, dispersion
    field/                   canvas renderer: float32 → colormap → ImageData; pan/zoom
    api/                     generated client from the FastAPI OpenAPI schema (openapi-typescript)
    state/                   zustand stores: selection, settings, jobs
    i18n/                    en.json, zh-CN.json (i18next); keys namespaced by feature
  e2e/                       Playwright: smoke per screen against a recorded sample result
```

- Stack: React 19 · TypeScript · Vite · Tailwind v4 · Radix UI primitives · react-three-fiber + drei · Apache ECharts · zustand · TanStack Query · react-router · i18next · vitest · Playwright. All MIT/Apache/ISC licensed; recorded in `THIRD_PARTY.md` like the Python side.
- Vite builds straight into `etalon/studio/static/` (gitignored), which FastAPI serves and the wheel includes; a hatch build hook refuses to build a wheel without it. The Python package has no Node dependency at runtime.
- Binary data path: field arrays go over `GET /api/results/{id}/fields/...` as `application/octet-stream` (header JSON with shape, dtype, extent, then raw float32); never JSON arrays.
- No global CSS beyond tokens; no CSS-in-JS runtime.

## 9. Backend contract (FastAPI, in `etalon/studio/server.py`)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/workspace` | folder, list of simulations with status/last run/backend/cells |
| `POST /api/simulations` | create from template `{template, name}` |
| `GET /api/simulations/{id}/spec` | execute script (subprocess, with overrides) → JSON spec + preview geometry (triangulated meshes, boxes, grid lines, slice permittivity) + estimate + warnings |
| `PUT /api/simulations/{id}/params` | store parameter overrides in sidecar |
| `POST /api/simulations/{id}/run` | start job → `{job_id}` |
| `WS /api/jobs/{job_id}` | `{step, total, energy, cells_per_s, eta_s, snapshot?}` ≤ 4 Hz; final `{status, result_id}` |
| `DELETE /api/jobs/{job_id}` | cancel |
| `GET /api/results/{id}` | metadata: version, sha, backend, GPU, settings |
| `GET /api/results/{id}/s-matrix` | `{wavelengths, ports, S: complex as [re, im]}` |
| `GET /api/results/{id}/fields/{monitor}?component=&plane=&index=&wavelength=` | binary float32 slice |
| `GET /api/results/{id}/modes/{monitor}` | n_eff, n_g, fractions, profile ids |
| `POST /api/modes/solve` | cross-section → modes (used by the Mode Solver page) |
| `GET /api/validation/latest` · `POST /api/validation/run` | benchmark report |
| `GET/PUT /api/settings` | settings |
| `GET /api/system` | etalon and Python versions, platform, CuPy status, detected CUDA devices (added in U0) |

Server binds to `127.0.0.1` only. CORS off. A random token, created on first launch and kept in the user's config directory, arrives once in the URL (`?token=`); the SPA keeps it in `localStorage` and sends it as `X-Etalon-Token` on every API request, which guards against other local processes. The server also rejects any `Host` other than `127.0.0.1:<port>` / `localhost:<port>` (DNS rebinding), serves `index.html` with a `default-src 'self'` Content-Security-Policy, and disables FastAPI's `/docs`, `/redoc` and native OpenTelemetry.

## 10. Milestones (interleaved with solver milestones in `mvp-spec.md`)

| Milestone | After solver | Deliverable | Accepted when |
| --- | --- | --- | --- |
| U0 Shell | M0 | `etalon studio` command, FastAPI skeleton, SPA with routing, Workspace list, Settings, design tokens + 8 core components, i18n wiring with en + zh-CN | Opens in < 2 s; lists a workspace of 50 scripts; language switch flips every string; Playwright smoke passes |
| U1 Setup | M1 | Structure tree, 3D viewport with slice/permittivity view, Inspector, parameters with apply-and-reload, estimate bar with warnings | The ring template renders correctly in all three planes; a wrong layer in a template is visibly wrong; estimate within ±30 % of the real run on the dev GPU |
| U2 Run | M1 | Job runner, WebSocket progress, energy decay chart, live snapshot, log, cancel, failure panel | A 3-minute run reports progress at ≥ 2 Hz; cancel returns within 2 s; OOM shows the suggestion |
| U3 Results | M2 | S-parameter chart with all views, field viewer with canvas renderer, modes tab, export (CSV/Touchstone/PNG), stale banner | A reviewer opens the ring result and reads FSR and Q in 30 s without help; Touchstone imports into an external tool cleanly |
| U4 Polish | M3 | Mode Solver page, Compare, Validation page, command palette, keyboard map, zh-CN review by a native speaker | Five example notebooks each have a Studio walkthrough in docs; no P1 accessibility issues (axe) |

## 11. Explicitly not in Studio MVP

Geometry editing / CAD · script editor (we open the user's editor) · multi-user / sharing server · auth · cloud sync · plugin system · GDS layout viewer beyond the imported structures · 3D volumetric field rendering (slices only) · mobile layout (desktop ≥ 1280 px; tablet read-only is acceptable if free).

## 12. Open questions

- [ ] Parameter declaration API: `et.param("radius", 10.0, unit="um")` vs reading module-level constants with a decorator? (recommend explicit `et.param`)
- [ ] Should Setup execute the user script in-process (fast) or subprocess (safe)? (recommend subprocess, cached by file hash)
- [ ] Time estimate calibration: a one-time 10-second benchmark on first launch, or learn from each run? (both — first launch seeds, runs refine)
- [x] Do we ship a light theme in MVP or dark only? Dark default + paper light + system, from U0 (`docs/plan-u0.md` §2).
