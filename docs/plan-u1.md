# U1 plan — the M0 demo: Setup, Run and the field viewer

Status: approved 2026-10-16 (all §10 recommendations accepted) · builds on U0 (PR Iamsohungrynow/etalon#1)

## 1. Scope (answered 2026-10-16)

Only solver M0 exists: 2D TE (Ex, Ey, Hz), Box geometry, point sources with a Gaussian pulse, DFT monitors, NumPy and CUDA backends. You chose a **real 2D demo on M0**. This milestone therefore takes the parts of spec U1–U3 that M0 can feed with real data:

| Spec milestone | In this plan | Waits for |
| --- | --- | --- |
| U1 Setup | structure tree, viewport (3D orbit + permittivity slice), inspector, estimate bar with warnings | parameters with apply-and-reload (needs an `et.param` API in core, a solver change) |
| U2 Run | job runner, WebSocket progress, energy decay, live field, log, cancel, failure panel | shutoff threshold line (the M0 solver has no shutoff) |
| U3 Results | field viewer (float32 over HTTP, canvas), point-monitor spectra, PNG/CSV export, stale banner | S-parameters, modes, Touchstone (M1–M2) |
| U0 extras | NumberField, Tree, Tabs, `/kitchen-sink`, zustand, 501 stubs for the rest of §9 | — |

The visual payoff comes from the physics (you chose "real physics, calm chrome"): the field of the actual run animating live, an orbitable 3D view of the structures, and the solver's own permittivity map under them. The chrome stays as U0 decided. Nothing is fake: every pixel comes from the solver.

Layout follows the visual reference you supplied (`docs/design/studio-reference.html`): Setup is tree | stage | inspector, and Results → Fields is canvas | inspector. The reference's black void stage becomes the viewport and the field canvas.

## 2. How Studio runs a user's script (no solver changes)

Studio never edits solver code. It runs the user's script in a subprocess and intercepts `Simulation.run` at runtime in that child process only, which is the same as running the script with an instrumented `etalon`:

- **Spec mode** (`GET /api/simulations/{id}/spec`): `Simulation.run` is replaced by a function that records the simulation and stops the script. A script that never calls `run()` falls back to the module-level `Simulation` objects it defines. The child returns `sim.model_dump()` (the core models already round-trip JSON), the Yee grid numbers, `summary()` values and warnings. Results are cached by the script's sha256, so an unchanged script costs nothing. A 60 s timeout kills a runaway script.
- **Run mode** (job): `Simulation.run` is replaced by Studio's stepping loop around the public `FDTDSolver`: `step()`, `n_steps`, `grid`, `fields()`, `result()`. The script then continues with a real `SimulationResult`, exactly as if it had run normally.

In both modes the subprocess runs `python -m etalon.studio.runner …` with the workspace folder as the working directory. Its stdout and stderr tail go to the log.

## 3. Endpoints

Implemented (types generated into the client as in U0):

| Endpoint | Returns |
| --- | --- |
| `GET /api/templates` · `POST /api/simulations` | template list; copy a template into the workspace `{template, name}` → row |
| `GET /api/simulations/{id}/spec` | spec JSON + preview geometry (region, PML, boxes, sources, monitors, all in µm) + estimate (cells, memory, steps, Δt, time estimate) + warnings; a script error → 422 with traceback and line number |
| `GET /api/simulations/{id}/permittivity?plane=xy` | **new**: binary float32 εr on the grid (header JSON: shape, extent, dx, dy) for the slice view |
| `POST /api/simulations/{id}/open` | **new**: opens the script in the OS default editor (spec §5.2 "Open in editor") |
| `POST /api/simulations/{id}/run` | `{job_id}` (one job at a time per simulation; 409 if one is running) |
| `WS /api/jobs/{job_id}` | JSON text frames `{step, total, energy, cells_per_s, eta_s, elapsed_s}` at ≤ 4 Hz, `{log}` lines, final `{status, result_id, error?, suggestion?}`; **binary frames**: live field snapshots (float32, header + data) at ≤ 10 fps (D4) |
| `DELETE /api/jobs/{job_id}` | cancel; partial DFT data is kept and the run is marked cancelled |
| `GET /api/results/{id}` | metadata: etalon version, backend, device, precision, grid, steps, Δt, wall time, cells/s, script sha256, monitors |
| `GET /api/results/{id}/fields/{monitor}?component=&quantity=&wavelength=` | binary float32 slice of a plane monitor (quantity: abs, real, imag, phase) |
| `GET /api/results/{id}/spectra/{monitor}` | **new**: a point monitor's complex spectrum vs wavelength, as small JSON (not a field array) |
| everything else in §9 (params, s-matrix, modes, modes/solve, validation) | **501** `{"code": "not_implemented", "endpoint": "<name>", "arrives_in": "U?/M?"}` |

**Run directory** (sidecar, Studio-owned until the solver's HDF5 output arrives in M3): `.etalon/<script>/runs/<UTC stamp>/` holds `meta.json`, `log.txt` and `result.npz` (every monitor component's complex array plus its coordinates). `status.json` (U0 format) gains `last_run`. The result id is `<sim id>~<stamp>`.

**Energy** (Run chart): the discrete field energy W = ½ ΔxΔy Σ(ε0 εr E² + μ0 H²), computed on the device from the solver's fields and update coefficients every progress tick, and plotted relative to its peak on a log axis.

**Live field**: Hz, downsampled on the device to ≤ 256 × 256 before the copy, so the cost on the GPU is negligible.

## 4. Screens

- **Workspace**: "New from template" now works (U0 D10 deferred it to U1). Running rows update live (refetched every second while one is running).
- **Setup** `/sim/:id/setup` (tree 240 px | stage | inspector 280 px):
  - Tree: media, structures, sources, monitors, boundary, grid. Selecting an object highlights it in the viewport and fills the inspector (one zustand selection store); each object can be hidden for viewing.
  - Stage, two views. **3D**: region slab, PML as a hatched shell, Boxes extruded by their z-extent and coloured by medium, sources as markers with their component, monitors as wireframes; orbit/pan/zoom (three's OrbitControls), `F` frames the selection. **Slice**: the solver's own εr map as an image with the grid lines (`G`) and outlines on top. The slice is the "visibly wrong" guarantee: it is what the solver will actually simulate, not a redraw of the script.
  - Inspector: read-only properties with units, through NumberField's display.
  - Estimate bar (always visible): cells, memory, steps, Δt, estimated time ("unknown" until this machine has a measured cells/s), and warnings: fewer than 20 cells per λ in the highest-index medium, PML thinner than λ/2, a source or monitor within 3 cells of the PML, more than 4 GB of memory. The Run button is disabled only on errors.
  - States: "Building simulation…" with the stdout tail; script error → traceback with the failing line highlighted.
- **Run** `/sim/:id/run`: progress bar (step / total, elapsed, ETA, cells/s), energy-decay chart (ECharts, log y), live field canvas (RdBu, symmetric scale, ≤ 10 fps), log view, Cancel (confirmation only after 1 min). On failure: the error, the traceback, and a one-line suggestion when we recognise it (out of memory → smaller grid or single precision; NaN → courant too high or a source inside a structure edge; 3D → "arrives in M1"). When done: a link to Results.
- **Results** `/sim/:id/results`:
  - Header: run metadata.
  - Tabs: **Fields** (monitor → component → quantity → wavelength → colormap/linear-log; canvas with pan/zoom, a hover readout of value and coordinates, the structure-outline overlay and 2× PNG export) · **Spectra** (point monitors: |F| and phase vs λ, a data-table toggle, CSV export) · **S-parameters** (disabled: "needs M2").
  - Stale banner when the script changed after the run.
- **Kitchen sink** `/kitchen-sink`: every component in every state, both themes. Not in the navigation; for review and the demo.

## 5. Components to add

| Component | API | Built on |
| --- | --- | --- |
| NumberField | `value: number` (SI base unit), `unit: "um" \| "nm" \| "s" \| "fs" \| "Hz" \| "THz"`, `onCommit(value)`, `display?: "um" \| "nm"`, `readOnly`, `min`, `max`, `step`, `label`. Parses "1.55", "1.55 µm", "1550nm", "1.55e-6 m", "0.5um"; ↑/↓ step, Enter commits, Esc reverts; invalid → inline error; shows 4 significant figures, full precision on focus | native input |
| Tree | `nodes: TreeNode[]` (`{id, label, icon?, children?, hidden?}`), `selectedId`, `onSelect`, `onToggleHidden`; arrow keys and Home/End per the WAI-ARIA tree pattern, `role="tree"` | — |
| Tabs | `value`, `onValueChange`, `tabs: {value, label, disabled?, hint?}[]`, `children` per panel | Radix Tabs |
| Chart | `series` (x, y, name, dashed), `yScale: "linear" \| "log"`, axis labels with units, `crosshair`, `table` toggle; Okabe–Ito colours | ECharts (tree-shaken: LineChart, Grid, Tooltip, DataZoom) |
| FieldCanvas | `data: Float32Array`, `shape`, `extent` (µm), `colormap: "viridis" \| "RdBu"`, `scale: "linear" \| "log"`, `symmetric`, `outline?`, `onHover(value, x, y)`; float32 → LUT → ImageData, pan/zoom, PNG export at 2× | canvas 2D |
| Viewport3D | `preview`, `selectedId`, `hidden`, `onSelect`; region, PML, boxes, sources, monitors | three + @react-three/fiber + three's OrbitControls |
| ProgressBar, LogView, Inspector (key–value), NumberDisplay | small, spec §7 list | — |

Colormaps: viridis (CC0) and RdBu (ColorBrewer, Apache-2.0) as 256-entry tables generated once from matplotlib by a script and committed (`studio/src/field/colormaps.ts`).

## 6. Templates (M0-capable, in `etalon/studio/templates/`)

All four are 2D TE, run in seconds on the GPU, and are real etalon scripts:

1. **vacuum_pulse**: `examples/00_vacuum_pulse.py`, a cylindrical wave and the quiet CPML.
2. **strip_waveguide**: an n = 3.476 strip in SiO2, an Hz point source at 1.55 µm, a plane monitor.
3. **sharp_bend**: two Boxes forming a 90° corner, showing what a sharp bend radiates.
4. **phc_waveguide**: a photonic-crystal line-defect waveguide (a square lattice of Si rods as Boxes with one row removed). The light stays in the defect line: the demo's centrepiece.

The five spec reference devices replace these at M1–M2.

## 7. Fixtures recorded from a real run

`studio/e2e/fixtures/workspace/` gains:

- `phc_waveguide.py` with a **real CPU run** recorded into its sidecar: `result.npz` with plane and point monitors at 3 wavelengths, `meta.json` and `log.txt`, about 1–2 MB. Recorded once by `studio/e2e/fixtures/record.py`, rerun only when the solver's output changes.
- `misplaced_strip.py`: the strip template with its Box shifted outside the source line (the "visibly wrong" case).
- `broken_script.py`: raises at line 12 (the traceback case).

Results tests read the recorded run, so no GPU is needed. The Run test runs the tiny strip template live on the CPU backend (a few seconds).

## 8. Tests

**pytest** (`tests/studio/`):
- spec capture: with `run()`, without it, and with an exception reporting its line number; the cache hit on the same sha; the timeout
- εr slice equals `permittivity_on_nodes` on the same grid
- the runner on the CPU: progress rate, energy finite and decaying after the pulse, snapshot shape ≤ 256², cancel within 2 s with partial results saved, a failing script → status failed with a traceback
- results endpoints: binary header/shape/dtype, quantity and wavelength selection, spectra JSON
- 501 stubs name their endpoint
- template creation: no overwrite, name validation

**vitest**:
- NumberField parsing and formatting (units, exponents, locales, errors)
- Tree keyboard navigation
- Tabs
- colormap LUT endpoints
- FieldCanvas: float32 → RGBA for known values, log scale, symmetric scale
- binary frame decoder
- the Setup, Run and Results screens' loading, empty and error states (fake server)

**Playwright** (built SPA, real server):
- **Setup**: renders `phc_waveguide` in 3D and the slice; for `misplaced_strip`, the slice pixel at the script's intended position is low-index and the high-index stripe sits where the solver put it.
- **Run**: the strip template starts, reports progress at ≥ 2 Hz, draws live frames, finishes, and Results opens; cancel returns within 2 s.
- **Results**: the recorded `phc_waveguide` run, where the hover value matches the stored array at a known point, PNG export downloads, and the spectra table matches `result.npz`.
- **Kitchen sink** renders. The P1–P9 smoke tests extend to the new routes, still with no console error and no request leaving 127.0.0.1.

## 9. Dependencies (licence-checked 2026-10-16)

| Package | Version | License | Note |
| --- | --- | --- | --- |
| websockets (Python) | 17.2 | BSD-3-Clause | uvicorn needs a WebSocket library; no dependencies of its own |
| three | 0.186.1 | MIT | |
| @react-three/fiber | 9.8.2 | MIT | |
| echarts (+ zrender) | 6.1.0 | Apache-2.0 (+ BSD-3-Clause) | tree-shaken; tslib 2.3 (0BSD) |
| zustand | 5.0.15 | MIT | |

Not taken: **@react-three/drei** (MIT). It pulls MediaPipe, the Rapier physics engine, hls.js and Draco into the tree, and a viewport of boxes needs only OrbitControls, which three itself ships (D6).

## 10. Decisions for review (say OK to take all recommendations)

1. **Script interception** as in §2: patch `Simulation.run` in the child process only, never in solver source.
2. **Run storage** as in §3: `result.npz` in the sidecar run folder until M3's HDF5. npz needs no new dependency (NumPy).
3. **Contract additions** to §9: templates, permittivity slice, open-in-editor, spectra. They go into ui-ux-spec §9 in the first commit.
4. **Live field at ≤ 10 fps** while progress messages stay ≤ 4 Hz, as the spec says. Snapshots are ≤ 256² float32 (≤ 256 KB) on localhost; 10 fps is what makes the wave read as motion. On the CPU backend, snapshots stay off by default (spec §5.3) and turn on with the existing Settings toggle.
5. **M0 templates** as in §6, including the photonic-crystal waveguide for the demo.
6. **No drei**: three's OrbitControls instead.
7. **Energy** as defined in §3. No threshold line until the solver gains a shutoff.
8. **Time estimate** from this machine's measured cells/s of earlier runs (stored in the config dir), plus a "Calibrate" button that runs `etalon.validation.throughput` for about 10 s. Before either, the estimate says "unknown".
9. **Parameters (`et.param`) are out**: they need a core API, which is solver work. I'll leave a note for the solver session.
10. **Two writers in parallel** (you asked for split work): a new session builds the server side (runner, spec capture, results and template endpoints, fixtures recording, pytest) under `etalon/studio/**` and `tests/studio/**`, from this plan's contract. This session builds the frontend under `studio/**` in parallel against the same contract. I merge their branch, regenerate the API types and run the full suite. The file sets don't overlap.

## 11. Order of work

1. Spec §9 additions; this plan approved.
2. *Server session*: runner + spec capture → results/templates endpoints → fixture recording → pytest.
3. *Here*: NumberField, Tree, Tabs, Chart, FieldCanvas, colormaps, kitchen sink + vitest.
4. *Here*: Setup (tree, viewport, slice, inspector, estimate) on the agreed contract.
5. *Here*: Run (WebSocket client, binary decoder, live canvas, energy chart, log, cancel, failure).
6. *Here*: Results (fields, spectra, export, stale banner).
7. Merge the server branch, regenerate the API client, run Playwright on every route, check THIRD_PARTY, README and the outcome section here.

## 12. Risks

- **Script side effects**: spec mode executes the user's script up to `run()`. A script that writes files or plots before `run()` does so on every Setup refresh (the sha cache limits this). This is the same trust model as running the script.
- **GPU in the server process**: none. Every solver run is in a child process, so a CUDA crash only kills the job.
- **Bundle size**: three, r3f and ECharts add roughly 900 KB minified. The routes split code, so Workspace still opens in under 2 s; P3 keeps guarding that.

## 13. API contract (the boundary between the server session and the frontend)

Both sides build to exactly this. The server's pydantic models define the OpenAPI schema, and the frontend's types are generated from it. Any change goes into this section first.

### 13.1 Binary arrays (permittivity slice, monitor fields, live snapshots)

One layout everywhere: `[uint32 little-endian N][N bytes UTF-8 JSON header][zero padding to a multiple of 4][float32 little-endian data]`. The data starts at `4 + N` rounded up to a multiple of 4, so the client views it as a `Float32Array` without copying. HTTP responses use `Content-Type: application/octet-stream`; WebSocket snapshots are binary frames.

The header contains:
- `kind`: `"permittivity"`, `"field"` or `"snapshot"`
- `shape: [n_x, n_y]`: the solver's own C order, with axis 0 = x and axis 1 = y, y varying fastest
- `extent: [x_first, x_last, y_first, y_last]`: µm, of the first and last nodes along each axis (uniform spacing)
- `min`, `max`: finite data range
- `component`, and `unit` (free text)

Per kind:
- **permittivity**: `pml_cells`.
- **field**: `quantity` (`abs | real | imag | phase`) and `wavelength_um`.
- **snapshot**: `step`. Downsampled to at most 256 × 256; its `extent` describes the downsampled nodes.

### 13.2 Simulations and templates

- `GET /api/templates` → `[{id, file}]`, with id in `vacuum_pulse | strip_waveguide | sharp_bend | phc_waveguide`. Titles and descriptions are i18n keys in the frontend, `templates.<id>.title/description`.
- `POST /api/simulations {template, name}` creates a script; `name` is a file name without `.py`, `[A-Za-z0-9_-]{1,64}`.
  - 201 → `SimulationRow`
  - 409 `{code: "exists"}`
  - 422 `{code: "bad_name"}`
- `SimulationRow` (U0) gains two fields: `job_id: str | null` (a running job) and `last_result_id: str | null`.
- `GET /api/simulations/{id}/spec` → `SimulationSpec`:
  - `script_sha256`
  - `spec`: free-form JSON, `Simulation.model_dump(mode="json")`
  - `preview`
  - `estimate`
  - `warnings`
  - `stdout_tail`
- `Preview`:
  - `is_2d`, `plane_z`
  - `region {center, size}`
  - `pml {layers, thickness: [tx, ty, tz]}` (µm)
  - `background {n, name}`
  - `media: [{id, name, n}]`
  - `structures: [{id, name, kind: "Box", center, size, medium_id}]`
  - `sources: [{id, name, kind: "PointSource", center, component, wavelength_um, bandwidth_um}]`
  - `monitors: [{id, name, kind: "DFTMonitor", geometry: "point" | "line" | "plane" | "box", center, size, wavelengths_um, components}]`
  - `grid {dx, dy, nx, ny, region_cells: [rx, ry], dt_s, courant, steps}`
  - Ids: `medium:<i>`, `structure:<i>`, `source:<i>`, `monitor:<name>`, `boundary`, `grid`.
- `Estimate`: `{cells, memory_bytes, steps, dt_s, run_time_s, seconds, cells_per_s, basis: "measured" | "calibration" | "unknown"}`. `seconds` and `cells_per_s` are null when the basis is unknown.
- `Warning`: `{code, severity: "warning" | "error", object_id | null, params}`. Codes and their params:
  - `mesh_coarse {cells_per_wavelength, minimum, medium, wavelength_um}`
  - `pml_thin {thickness_um, half_wavelength_um}`
  - `near_pml {cells}`
  - `memory_large {bytes}`
  - `unsupported {feature, milestone}`, which is an error (e.g. 3D → M1)

  The frontend translates codes; the server never sends prose.
- Script failure: 422 `ScriptError {code: "script_error", message, traceback, line | null, stdout_tail}`. A timeout uses `code: "script_timeout"`.
- `GET /api/simulations/{id}/permittivity?component=Ex|Ey` (default Ex) → binary `kind: "permittivity"`: the solver's own εr array on those nodes, PML included.
- `POST /api/simulations/{id}/open` → 204, opens the script in the OS default editor.
- `POST /api/calibrate` → `{cells_per_s, backend, device}`: about 10 s of `etalon.validation.throughput`, stored in the config dir and then used by `Estimate`.

### 13.3 Jobs

- `POST /api/simulations/{id}/run` → 202 `{job_id, result_id}`; 409 `{code: "already_running", job_id}`.
- `DELETE /api/jobs/{job_id}` → 202 `{status: "cancelling"}`. The final status arrives on the WebSocket.
- `WS /api/jobs/{job_id}`: the browser cannot set headers on a WebSocket, so it opens with subprotocols `["etalon.v1", "token.<token>"]`; the server accepts with `etalon.v1`. On connect the server replays `started`, then one `history`, then sends live messages. JSON text frames:
  - `{type: "started", total, grid: [nx, ny], dt_s, backend, device, snapshots: bool}`
  - `{type: "history", progress: [Progress...], log: [LogLine...]}` (every progress point so far and the last 500 log lines)
  - `Progress {type: "progress", step, total, elapsed_s, eta_s, cells_per_s, energy}`, at ≤ 4 Hz; `energy` is absolute (J/m in 2D) and the client normalises it to the peak
  - `LogLine {type: "log", stream: "stdout" | "stderr" | "etalon", line}`
  - `{type: "done", status: "done" | "failed" | "cancelled", result_id | null, error: {message, traceback, line} | null, suggestion: "out_of_memory" | "nan" | "unsupported" | null}`

  Binary frames are `snapshot`s (Hz, ≤ 10 fps), only when snapshots are on: the Settings toggle, which on the GPU defaults to on for the demo.
- The runner keeps `status.json` (U0 format) current while running, with step, total and ETA, so the Workspace shows live progress.

### 13.4 Results (`result_id = <sim id>~<UTC stamp>`)

- `GET /api/results/{id}` → `ResultMeta`:
  - `result_id`, `simulation_id`, `status`, `started_at`, `finished_at`
  - `etalon_version`, `backend`, `device`, `precision`
  - `grid {nx, ny, dx, dy}`, `steps`, `dt_s`, `wall_time_s`, `cells_per_s`
  - `script_sha256`, `stale`
  - `preview`: the Preview at run time, used for outline overlays
  - `monitors: [{name, geometry, components, wavelengths_um, shape | null, extent | null}]`
- `GET /api/results/{id}/fields/{monitor}?component=&quantity=abs|real|imag|phase&wavelength_index=` → binary `kind: "field"`, for plane and line monitors.
- `GET /api/results/{id}/spectra/{monitor}` → `{monitor, wavelengths_um, components: {<C>: {re: [...], im: [...]}}}`, for point monitors.

### 13.5 Still 501

These return `{code: "not_implemented", endpoint, arrives_in}`:
- `PUT /api/simulations/{id}/params`: U1 + an `et.param` core API
- `GET /api/results/{id}/s-matrix`: M2
- `GET /api/results/{id}/modes/{monitor}`: M1
- `POST /api/modes/solve`: M1
- `GET /api/validation/latest`, `POST /api/validation/run`: U4

## 14. Outcome (2026-10-16)

Built as planned: the server side in its own session (`claude/u1-server-af24bb`, merged here), the frontend in this one, with three subagents for the components (forms and tree, field canvas, chart and 3D viewport).

| Check | Result |
| --- | --- |
| U1 Setup: the template renders; a wrong layer is visibly wrong | Playwright: the photonic-crystal template shows its tree, 3D view, estimate and slice. Hovering the slice centre reads εr = 12.08 (Si, the line defect). For `misplaced_strip.py` it reads 2.085 (SiO2): the strip is not where the script meant it |
| U2 Run: progress ≥ 2 Hz, cancel within 2 s | Playwright: a real CPU run of the strip template from "New from template" streams progress at ≥ 2 Hz, live Hz frames, the log, finishes and opens its Results. Cancel shows "cancelled" within 2 s and keeps the data |
| Field viewer, float32 over HTTP, canvas | Playwright: on the recorded photonic-crystal run, the hover value equals the stored array at that node (to 1e-4), and PNG and CSV export download |
| pytest (whole repository) | 344 pass, 2 skipped (POSIX-only) |
| vitest | 257 pass |
| Playwright | 20 of 21 pass; P3 (open time) fails, see below. Checked by hand in the browser too: Setup's 3D view of the photonic crystal, a live GPU run (13 s, the guided wave forming in the line defect), the recorded run's field |
| ruff, mypy, ESLint, tsc | clean |

**P3, open time, now over budget.** `etalon studio` to 50 rows measured 2.28–2.38 s over three runs at 35–50 % background CPU load, against the 2 s budget (U0: 1.65–1.68 s).
- U1 adds about 0.25 s of start-up: the API contract's pydantic models (0.12 s), FastAPI building more routes, and uvicorn loading `websockets`.
- The GPU probe now starts only once the server listens, so its CuPy import no longer competes with Studio's own start-up.
- Later in the session the machine slowed about threefold for every process (`import numpy` 0.29 s → 1.04 s), and P3 read 5.9 s; that is not a Studio change.
- The remaining large cost is `import etalon` itself (≈ 0.8 s here: NumPy and pydantic for `core`). U0 D1 said I would report this rather than make every name in `etalon/__init__.py` lazy, so this is a decision for you.

Departures from the plan:
- **The photonic-crystal template is air holes in silicon, not rods.** In 2D TE a rod lattice has no band gap; with holes, 99–100 % of the field stays in the line (server session).
- **The first solver step takes 5–9 s.** The solver builds DFT phase tables for far more steps than a run needs. The fix is `f65c187` on `claude/gallant-wescoff-7b247c` (solver session), not merged here. Until it lands, Run shows "Preparing the solver…" for those seconds.
- **Contract additions beyond §13** (server session):
  - `Preview.grid` and the estimate are null for 3D scripts.
  - A `no_simulation` script error.
  - A row status reason `interrupted`.
- **Response types are restored at one place.** openapi-fetch types responses as `Readable<T>`, which widens tuples to arrays, so `queries.ts` restores the generated component types where data comes in (`asSchema`). No type is written by hand.
- **The Run screen keeps following its job** after the row's `job_id` clears. Otherwise it would drop the finished outcome; a vitest regression test covers this.
- **Viewport details** (subagent):
  - Overlapping 2D boxes are drawn slightly staggered, so the box the solver lets win shows on top.
  - Boxes are clipped to the domain.
  - Translucent boxes (the photonic crystal's air holes) cut themselves out of the slab.
- **Colour scale and image share one range** (`resolveRange`), as the field-canvas subagent pointed out.
- **The 3D view was blank on first load** until the window resized: it framed its camera before the canvas had a size. Found by looking, since the test only checked that the canvas existed. Fixed (`viewport/SizeWatcher.tsx`), and the Setup test now checks that the viewport actually draws.
- **Not done:** parameters (`et.param`, a core API), the shutoff threshold line on the energy chart, and S-parameters, modes and 3D (M1–M2).

### 14.1 P3 open time: findings and proposal (2026-10-16, side session; awaiting OK)

Measured on the Windows dev machine (Ryzen 5 5600), with the CPU load checked before each series. "Moderate load" below is 5 busy processes on 12 threads (30–40 % CPU). Each option was prototyped in a scratch copy of the package and timed against the others in alternation; nothing is committed.

**Where the time goes.** P3 at baseline (a874fda) runs 1.84–2.02 s idle and 2.11–2.23 s under moderate load. Almost all of it is the server: spawn → GET / answers in ≈1.6 s idle. The browser part is ≈0.2 s (0.3 s inside P3 with its route guards): JS is loaded by 26 ms and `/api/workspace` is requested at ≈110 ms. In-process, idle:

| Step | Time |
| --- | --- |
| Process start (venv launcher + interpreter) | 0.06 s |
| `import etalon` (`etalon/__init__.py`): NumPy 0.24 s, pydantic 0.3 s, `core` models ≈0.2 s | 0.69 s |
| Studio + FastAPI + uvicorn on top. FastAPI 0.30 s, uvicorn 0.17 s, contract models 0.12 s; `routes`, `jobs` → `runner` also import NumPy and `etalon.core` | 0.61 s |
| `create_app`: 75 ms is FastAPI importing `pydantic.v1` to reject v1 models | 0.09 s |
| uvicorn until listening (loads its h11 and WebSocket protocol modules) | 0.10 s |

FastAPI + uvicorn alone take 0.93 s in a fresh process here. Nothing Studio does can go below that floor.

**Options** (median of 9 interleaved runs, idle; P3 = three runs each):

| Variant | Listening | `/api/workspace` answered | First U1 request answered | P3 idle | P3 moderate load |
| --- | --- | --- | --- | --- | --- |
| Baseline | 1.56 s | 1.64 s | 1.65 s | 1.84–2.02 s | 2.11–2.23 s |
| (a) all names in `etalon/__init__.py` lazy | 1.61 s | 1.67 s | 1.69 s | — | — |
| (b) quick app first, U1 routes added after listening | 1.53 s | 1.63 s | 1.69 s | — | — |
| (a) + (b), full app built at once after listening | 1.26 s | 1.45 s | 1.68 s | — | — |
| **(a) + (b), full app built after the first `/api/workspace`** | 1.24 s | 1.33 s | 1.66 s | 1.52–1.70 s (and one 2.42 s during a load spike) | **1.71–1.76 s** |
| … + (c) skip FastAPI's `pydantic.v1` import | 1.19 s | 1.27 s | 1.68 s | 1.56–1.77 s | 1.63–1.64 s |

- **(a) alone saves nothing for Studio.** pydantic is needed by FastAPI anyway. NumPy and `etalon.core` still load through Studio's U1 modules: `routes.py`, `binary.py`, `results.py`, `preview.py`, and `jobs.py` via `runner.py`.
- **(b) alone saves 0.07 s.** `import etalon.studio.*` runs `etalon/__init__.py` first, so NumPy and `core` still load before listening.
- **Together they save ≈0.3 s.** Start-up then imports only FastAPI, uvicorn, pydantic and Studio's U0 modules.
- **The full app must not be built while the Workspace loads.** Its imports hold the GIL and slow `/api/workspace` by ≈0.1 s. Built after the first Workspace response, it costs the first screen nothing. A U1 request still answers at the same time as today, because it waits for the build.

**Ruled out:**
- **The P3 poll is not the problem.** In Python, a refused connection to 127.0.0.1 takes 2 s on Windows: the SYN is retried every 0.5 s. Node's `fetch`, which P3 uses, fails at once (libuv), so P3 measures the server correctly.
- **Moving the GPU probe later** makes no difference to the browser part.
- **The SPA is not the bottleneck.** Its heavy screens are already split off.
- **Serving the first page without FastAPI** would mean a second, hand-written copy of the Workspace endpoints. That is not worth 0.1–0.2 s.

**Proposal: (a) + (b), with the build after the first Workspace response; (c) held in reserve.**
1. **(a) `etalon/__init__.py`, a shared solver file, so it needs your OK.** Every public name loads on first use (PEP 562), extending D1's lazy `analysis`/`SimulationResult` to all names. `import etalon` becomes ≈0.03 s, and the first `et.Simulation` pays the same 0.5 s as before. `TYPE_CHECKING` imports keep mypy and IDE completion. `__dir__`, `__all__` and `from etalon import *` keep working. The public API is unchanged. One cost: a broken NumPy install shows its error at the first `et.<name>`, not at `import etalon`. `tests/unit/test_package_import.py` gains two tests: `import etalon` loads no NumPy and no `etalon.core`, and every name in `__all__` resolves. The solver branch (`f65c187`) does not touch this file.
2. **(b) inside `etalon/studio/`.** `create_app(state)` stays the full app, for tests and `openapi.py`. `create_app(state, full=False)` registers only U0's routes and the SPA. `launch.py` serves both through a small ASGI wrapper:
   - The wrapper answers `/`, the assets, `/api/workspace`, `/api/settings` and `/api/system` from the quick app.
   - It builds the full app in a thread after the first `/api/workspace` response, or as soon as any other `/api` or WebSocket request arrives. That request waits for the build.
   - If the build fails, waiting requests get a 500 with an error code, never a hang.
   - `StudioState` creates `JobManager` and `SpecCache` on first use, so the quick app needs neither.
   - Studio has no lifespan handlers (`JobManager` uses `atexit`), so serving lifespan from the quick app changes nothing.
3. **Tests.**
   - `tests/studio/test_cli.py` S14 gets a second guard: after `import etalon.cli, etalon.studio.launch` and building the quick app, `sys.modules` holds no `numpy` and no `etalon.core`, `etalon.studio.routes`, `contract` or `runner`.
   - New tests for the wrapper: a U1 request before the build waits and succeeds; the first Workspace response starts the build; a failing build answers 500.
   - Then P3 three times, idle and under the 5-process load.
4. **(c) only if (a) + (b) is not enough.** Setting `sys.modules["pydantic.v1"] = None` in `launch.py` makes FastAPI's v1 check take its `ImportError` path and saves ≈0.08 s. It relies on a FastAPI internal and affects the whole server process, so I would not add it unless P3 still fails.
