# U0 plan — Studio shell

Status: approved 2026-10-16 (all §8 recommendations accepted) · Studio milestone U0 of `ui-ux-spec.md` §10 (gated on M0, which is done)

## 1. What U0 delivers

`etalon studio [FOLDER]` starts a FastAPI server on `127.0.0.1:8787` and opens Studio in the browser. U0 has two working screens, **Workspace** and **Settings**. It also has the app shell (header, navigation, spectrum stripe, status strip), the design tokens for dark and paper-light, the core components, and English + 简体中文 through i18next. Every other route already exists, so deep links resolve, and shows a "not in this version yet" state.

Acceptance (`ui-ux-spec.md` §10):

| Criterion | How it is measured | Pass |
| --- | --- | --- |
| Opens in < 2 s | P3: Playwright spawns `etalon studio --no-browser` on a 50-script workspace (t0), loads the page and waits until the table says 50 simulations (t1). Browser start-up is excluded. | t1 − t0 < 2 s on this machine, idle |
| Lists a workspace of 50 scripts | S8 (scan) and P2 (UI) | all 50 listed, the count says 50, the last row is reachable |
| Language switch flips every string | P4: after switching to 简体中文, no visible text outside `translate="no"` data contains a Latin letter, on every route | 0 offenders |
| Playwright smoke passes | P1–P9 | all green, with no console errors and no request leaving `127.0.0.1` |

Also: pytest, vitest, ruff, mypy, ESLint and `tsc` all clean.

Not in U0: the content of Setup, Run, Results, Mode Solver and Validation; "New from template" (D10); the command palette and keyboard map beyond Tab/Enter; the manual update check (it is a network call, so it waits for U4 with a decision on where it checks); zustand (no client state needs it until the U1 selection store); charts; 3D.

## 2. Reference decisions (answered 2026-10-16)

`docs/design/studio-reference.html` against `ui-ux-spec.md` §7:

| Conflict | Decision |
| --- | --- |
| Theme | Dark stays the default. The reference's paper palette replaces §7's light tokens. |
| Accent | Amber `#E8B34A` stays the one accent for selection, focus and primary actions. The spectrum appears once, as a static 2 px stripe under the header. It is `aria-hidden` and never sits behind text or data. |
| Tickers, particles | Dropped. One static bottom status strip shows real values: backend and device, workspace, simulation count, etalon version, "offline". |
| Shape | Taken from the reference: square corners, crisper 1 px rules, uppercase mono micro-labels. Kept from §7: 13 px body, 12 px dense tables, 15/18/22 px headings. |
| Fonts | Inter and JetBrains Mono bundled, never fetched (a rule, not a choice). |
| Random data, placeholder people | Not shipped (a rule). |
| Crosshair cursor | Only over canvases and the viewport, from U1 (D13). |

The first U0 commit writes these into `ui-ux-spec.md` §7 and `docs/design/README.md`.

## 3. Files

```
pyproject.toml           + fastapi, uvicorn (D5); [project.scripts] etalon = "etalon.cli:main";
                           dev: httpx; wheel includes etalon/studio/static (built, gitignored)
hatch_build.py           refuses to build a wheel without etalon/studio/static/index.html
                           (editable installs skip the check)
etalon/
  __init__.py            D1 only: `analysis` loaded lazily
  cli.py                 `etalon studio …`, `etalon --version`
  studio/
    __init__.py
    server.py            create_app(): /api routes, SPA fallback, index.html with theme and lang
    security.py          token, Host check, X-Etalon-Token check, CSP
    settings.py          StudioSettings, config dir, atomic load/save
    workspace.py         scan(): rows from *.py and their sidecar status.json
    system.py            versions + GPU probe (subprocess, cached)
    gpu_probe.py         standalone script run by system.py; imports cupy only, never etalon
    openapi.py           python -m etalon.studio.openapi → studio/src/api/openapi.json
    static/              built SPA (Vite outDir, gitignored)
studio/                  pnpm, TypeScript strict
  package.json  pnpm-lock.yaml  tsconfig.json  vite.config.ts  eslint.config.js
  playwright.config.ts  index.html
  src/
    main.tsx
    app/                 App (providers) · routes · Shell · StatusStrip · NotYetScreen
                         · NotFoundScreen · SessionEndedScreen
    features/workspace/  WorkspaceScreen · WorkspaceTable · StatusCell · rowTarget
    features/settings/   SettingsScreen and one file per section
    components/          one component per file (§5.5)
    api/                 openapi.json + schema.ts (both generated) · client.ts · queries.ts · token.ts
    i18n/                index.ts · en.json · zh-CN.json
    format/              numbers.ts · time.ts
    styles/              tokens.css · index.css
  e2e/                   *.spec.ts · guards.ts · fixtures/workspace/ · fixtures/makeWorkspace.ts
tests/studio/            pytest (§6)
```

No file under `etalon/fdtd`, `grid`, `analysis` or `validation` changes. `etalon/__init__.py` changes only if you OK D1.

## 4. Backend

### 4.1 The command

```
etalon studio [FOLDER] [--port 8787] [--no-browser]
```

- FOLDER defaults to the current directory, like `jupyter lab`. A missing folder exits with code 2 and says so.
- It binds `127.0.0.1` only, and there is no `--host` option.
- If the port is busy, it exits with code 2 and prints `port 8787 is in use; is Studio already running? Use --port to pick another`.
- It prints the workspace, the URL with its token and "Ctrl+C to stop", then opens the default browser unless `--no-browser` is given.
- uvicorn runs at log level `warning` with the access log off; errors go to the console.

### 4.2 Security

The guards from `ui-ux-spec.md` §9:

- **Token.** 32 random bytes, created on first launch in `<config>/studio-token` and reused after that (D6). `ETALON_STUDIO_TOKEN` overrides it for tests and automation. The SPA moves `?token=` from the URL into `localStorage`, which is scoped per origin and so per port, then removes it from the address bar. Every API request carries `X-Etalon-Token`; U2's WebSocket will carry it as a subprotocol. A missing or wrong token gets `401 {"code": "unauthorized"}`; the comparison uses `secrets.compare_digest`. Static assets and `index.html` need no token, because they hold no data.
- **Host check.** The `Host` header must be `127.0.0.1:<port>` or `localhost:<port>`; anything else gets 400. This blocks DNS-rebinding attacks.
- **No CORS.** Without CORS headers the browser blocks cross-origin reads, and the custom header forces a preflight that fails.
- **CSP** on `index.html` (D16): `default-src 'self'; connect-src 'self'; img-src 'self' data: blob:; font-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`. The browser itself then refuses any external fetch. Radix injects one `<style>` element for scroll locking, which is why `style-src` needs `'unsafe-inline'`.
- **FastAPI's docs off.** `/docs` and `/redoc` load Swagger UI from a CDN, so both are disabled. The schema is served at `/api/openapi.json`, behind the token.
- **FastAPI's telemetry off** (D2). FastAPI 0.143 ships native OpenTelemetry. It exports only if `FASTAPI_OTEL_AUTO_CONFIGURE=true` and an OTLP endpoint are set in the environment, or if another library in the process installs a provider. Studio passes `telemetry={"tracing": False, "metrics": False, "logs": False, "auto_configure": False}`, and the explicit config overrides the environment.

### 4.3 Endpoints in U0

| Endpoint | Returns |
| --- | --- |
| `GET /api/workspace` | `{folder, simulations: SimulationRow[], truncated}`; `404 {"code": "workspace_missing"}` if the folder has gone |
| `GET /api/settings` | `StudioSettings` |
| `PUT /api/settings` | the full new settings, validated; `422` with per-field errors |
| `GET /api/system` | **new, D11:** `{etalon_version, python_version, platform, cupy, devices[]}` |

The rest of §9 arrives with U1–U4.

**SimulationRow:** `id`, `name` (file name), `path` (relative, POSIX separators), `status` (`draft | running | done | failed | cancelled | unknown`), `status_reason`, `last_run` (ISO 8601 UTC), `backend` (`cuda:0`, `cpu`), `device`, `cells`, `wall_time_s`, `step`, `total_steps`, `eta_s`, `stale`, `modified`. Fields that don't apply are `null`.

- **id** (D7): the first 12 hex characters of sha256 of the relative POSIX path. It stays stable while the file isn't moved, and is URL-safe on every OS: `/sim/3f2a9c1e04b7/results`. The readable path is shown everywhere a row is.
- **Scan:** recursive. It skips names that start with `_` or `.` (which covers `__pycache__`, `.etalon`, `.venv`, `.git`) and directories that contain `pyvenv.cfg` or are named `node_modules` or `site-packages`. It doesn't follow symlinked directories. It stops at 5 000 scripts with `truncated: true`, which the UI shows as a banner. Rows are sorted by path, case-insensitively.
- **Sidecar** (D8): `<script's folder>/.etalon/<script name>/status.json`. Studio's job runner writes it from U2; U0 only reads it. It holds `{status, started_at, finished_at, backend, device, cells, wall_time_s, step, total_steps, eta_s, script_sha256}`. No sidecar means `draft`. An unreadable or invalid file gives `unknown`, with the reason in `status_reason`; the scan never fails because of one file. A row is `stale` when the run has finished and the script's sha256 no longer matches `script_sha256`. A content hash is used rather than mtime, so a `git checkout` that changes nothing doesn't mark rows stale. A crashed process can leave `running` behind forever; U2 adds a heartbeat for that.

**StudioSettings:** `backend` (`auto | cpu | cuda:N`), `language` (`system | en | zh-CN`), `theme` (`dark | light | system`), `units` (`um | nm`), `live_snapshots` (default off), `workspace` (absolute path). Every field except `workspace` is saved to `<config>/studio.json`:

| OS | Config directory |
| --- | --- |
| Windows | `%APPDATA%\etalon` |
| macOS | `~/Library/Application Support/etalon` |
| Linux | `$XDG_CONFIG_HOME/etalon`, default `~/.config/etalon` |

`ETALON_CONFIG_DIR` overrides the location for tests. The file is written atomically (temp file + replace). If it is unreadable, Studio uses the defaults and prints a warning instead of crashing; unknown keys are dropped. Changing `workspace` points the running server at another folder after checking that the folder exists. `backend` is only stored in U0; U2 passes it to jobs (`cpu` → `"numpy"`, `cuda:N` → `"cuda"` on device N, which needs device selection from the solver).

**GPU probe:** a thread started with the server runs `python gpu_probe.py` with a 20 s timeout. It returns `[{index, name, memory_bytes, compute_capability}]`, or `cupy: "missing"` or `"error: …"`. `GET /api/system` waits for the result, and the UI shows "Detecting GPU…" in the meantime. It runs in a subprocess for three reasons: `import cupy` costs about a second, it would load CUDA into the server, and a broken driver must not hang or crash Studio.

### 4.4 Serving the SPA

- `/` and every path outside `/api` and `/assets` return `index.html`, with `<html lang data-theme>` filled from the settings so the first paint has the right theme. `system` is resolved in CSS with `prefers-color-scheme`, so no inline script is needed.
- Hashed `/assets/*` get a long cache lifetime; `index.html` gets `no-cache`.
- If the SPA isn't built, `/` serves a short bilingual developer page that says to run `pnpm --dir studio build`, and the CLI prints the same message.
- In development, Vite runs on `127.0.0.1:5173` and proxies `/api` to 8787.

### 4.5 OpenAPI → TypeScript

`python -m etalon.studio.openapi` writes `studio/src/api/openapi.json` (sorted keys, stable output). `pnpm gen:api` runs `openapi-typescript` on that file to produce `src/api/schema.ts`. Both files are committed. S13 fails when the JSON is stale and V9 fails when the TypeScript is stale. `openapi-fetch` turns `schema.ts` into a typed client, so no request or response type is written by hand.

## 5. Frontend

### 5.1 Shell

- **Header (40 px):** the wordmark "etalon Studio" (`translate="no"`) and navigation to Workspace and Settings. Mode Solver and Validation stay hidden until U4 (D9).
- **Spectrum stripe:** 2 px, static, directly under the header.
- **Status strip (24 px, bottom):** JetBrains Mono 11 px with uppercase micro-labels: `BACKEND cuda:0 · RTX 4060 Ti · 8.0 GB │ WORKSPACE C:\…\rings │ 50 SIMULATIONS │ ETALON 0.0.1 │ OFFLINE`. Every value is real, taken from `/api/system`, `/api/settings` and `/api/workspace`. Skeletons show while loading, and nothing moves.
- **Routes:** `/`, `/sim/:id/setup`, `/sim/:id/run`, `/sim/:id/results`, `/modes`, `/validation`, `/settings`, `*`. A `/sim/:id/*` route shows the simulation's name and path with "Setup is not in this version yet" and a link back. An id that isn't in the workspace gives "No simulation with this id in the workspace". `*` is a 404 screen.
- **Session:** a 401 from any query replaces the page with "This Studio session has ended. Run `etalon studio` again and use the link it prints."

### 5.2 Workspace (`/`)

The wireframe in §5.1 of the spec, without `[New ▾]` (D10):

- **Toolbar:** the folder path, a filter field (⌕, matches name and path on the client) and a Rescan icon button. The query also refetches when the window regains focus.
- **Table:** Name · Status · Last run · Backend · Cells · Time, virtualised, 28 px rows in 12 px text, with a sticky header in uppercase mono.
  - Name: the file name, with its folder dimmed before it.
  - Status: a glyph plus a label (● done, ◐ running, ○ draft, ✕ failed, ⊘ cancelled, ? unknown), plus a "stale" tag. The colour is always backed by the glyph and the word.
  - Last run: "14:02 today", "yesterday 09:10" or a date, via `Intl` in the active language. A running row shows "step 11 k / 26 k".
  - Backend: `cuda:0` or `cpu`. Cells: SI prefixes, e.g. 42.3 M. Time: wall time `3m12`, or the ETA `~2m` while running.
- **Rows are links:** draft and unknown go to Setup, running to Run, done, failed and cancelled to Results. Because they are links, middle-click and "copy link" work.
- **States:**
  - Loading: 8 skeleton rows and "Scanning workspace…".
  - Empty: "No Python scripts in this folder. Add a simulation script (.py) here, or choose another folder in Settings."
  - Filter with no matches: "No scripts match 'xyz'".
  - Error: an ErrorPanel with the message and Retry, plus an "Open Settings" link if the folder is missing.
- **Banners:** "No CUDA device found; runs use the CPU backend" with a Settings link, which never blocks anything; and a banner when the scan stopped at 5 000 scripts.

### 5.3 Settings (`/settings`)

The sections follow §5.7 of the spec, each headed by an uppercase mono label. Every change saves at once with `PUT`, without a Save button. Updates are optimistic and roll back on error, with the error shown inline under the control (§6 of the spec: errors stay where they happened).

1. **Backend:** a Select (Auto · CPU · `cuda:0 RTX 4060 Ti 8.0 GB` …) and the detected devices (name, memory, compute capability). While detection runs it shows "Detecting GPU…". With no device, it shows the no-CUDA message. A probe failure shows the error text.
2. **Workspace folder:** a TextField in mono with an Apply button. The server checks the folder, an invalid one gets an inline field error, and the Workspace query refetches on success.
3. **Language:** a Segmented control with System / English / 简体中文. Each language name is written in that language and marked `translate="no"`.
4. **Theme:** a Segmented control with Dark / Light / System.
5. **Units:** a Segmented control with µm / nm (stored now, used from U1).
6. **Live-field snapshots:** a Toggle (stored now, used from U2).
7. **Privacy:** "Studio makes no network requests. Fonts and assets are bundled. Nothing leaves this machine."
8. **About:** etalon version, Python version, platform, and the third-party licences (a link to the bundled OFL texts and `THIRD_PARTY.md`).

### 5.4 Design tokens (`styles/tokens.css`)

CSS custom properties per theme on `<html data-theme>`, mapped into Tailwind v4 with `@theme` so classes read `bg-surface`, `text-muted`, `border-rule`. There is no other global CSS.

| Token | Dark (default) | Light (paper) | Notes |
| --- | --- | --- | --- |
| bg | `#0E1013` | `#F2F0E4` | |
| surface | `#15181D` | `#FFFFFF` | |
| raised | `#1C2027` | `#E8E6D9` | also the hover colour in dark |
| hover | `#1C2027` | `#E4E2D6` | |
| rule | `#3A414C` | `#000000` | panel and section rules; crisper than §7's `#2A2F38` |
| rule-subtle | `#2A2F38` | `#C9C7BA` | table row separators |
| control | `#6B7380` | `#000000` | input and button outlines, ≥ 3:1 (WCAG 1.4.11) |
| text | `#ECEEF2` | `#000000` | 14.1–21:1 |
| secondary | `#A6ADBA` | `#444444` | ≥ 7.2:1 |
| muted | **`#858D9A`** | `#666666` | §7's `#6B7380` is 3.98:1 on bg, below AA (D12) |
| accent | `#E8B34A` | `#B8862B` | in light, a fill only (2.8:1 as text) |
| accent-ink | `#E8B34A` | `#7A5A12` | accent text and focus ring, ≥ 5:1 |
| on-accent | `#0E1013` | `#000000` | text on accent fill: 10:1 dark, 6.5:1 light |
| ok | `#4CC38A` | `#166B3C` | |
| warn | `#E8B34A` | `#7E5C14` | equal to accent, as in §7 (D12) |
| error | **`#EC5D62`** | `#B3261E` | §7's `#E5484D` is 4.17:1 on raised (D12) |
| spectrum | the reference gradient `#ff0000 → #8f00ff` | same | stripe only |

Every text colour passes 4.5:1 against bg, surface and raised, checked with a script that runs as V3.

Type: "Inter Variable", then "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", system-ui. Numbers use "JetBrains Mono Variable" with `tabular-nums`. Sizes are 13 px body, 12 px tables, 15/18/22 px headings at weight 600, and 10–11 px micro-labels in uppercase mono with 0.08em tracking. Corners are square (radius 0). Rules are 1 px, with no shadows. Motion is 120 ms ease-out on panels and 0 under `prefers-reduced-motion`. The focus ring is a 2 px `accent-ink` outline. The fonts' greek subsets are included, so λ and Δ render in Inter.

### 5.5 Components

The spec asks for 8 core components. The two U0 screens need these 10, plus two small helpers:

| Component | Built on | Used by |
| --- | --- | --- |
| Button | Radix Slot (`asChild` for links) | Apply, Retry, empty-state actions |
| IconButton | Radix Slot; requires an `aria-label` | Rescan, clear filter |
| TextField | native `<input>` | filter, workspace folder |
| Toggle | Radix Switch | live snapshots |
| Segmented | Radix ToggleGroup | language, theme, units |
| Select | Radix Select | backend |
| Table | `@tanstack/react-virtual` | Workspace |
| Banner | — | no GPU, truncated scan |
| EmptyState | — | empty workspace, not-yet screens |
| ErrorPanel | — | every error state, with Retry |
| *Skeleton* | — | loading states; always paired with text, never a bare spinner |
| *Value* | — | data in mono with `translate="no"`: file names, paths, numbers with units, device names |

Each component is one file with typed props, no `any`, a visible focus ring and Lucide icons at 16 px.

### 5.6 i18n

- i18next and react-i18next, with the resources bundled (no HTTP backend). There is one file per language, `en.json` and `zh-CN.json`, with keys namespaced by feature: `app.*`, `nav.*`, `workspace.*`, `status.*`, `settings.*`, `errors.*`, `notYet.*`.
- Language "system" means `navigator.language`: anything starting with `zh` gives zh-CN, everything else en. Numbers and dates go through `Intl` in the active language, and unit symbols stay as symbols.
- ESLint's `i18next/no-literal-string` rule, in JSX mode, fails any literal UI string.
- Data is rendered through `Value` (`translate="no"`). That is also how P4 tells data apart from UI text.
- I write the zh-CN strings. A native speaker reviews them in U4, as §10 of the spec plans.

## 6. Tests

**pytest**: `tests/studio/`, CPU only, under 10 s, using httpx `TestClient` and subprocesses.

| ID | Test |
| --- | --- |
| S1 | binding: the CLI subprocess answers on 127.0.0.1; uvicorn's `Config.host == "127.0.0.1"`; no option changes it |
| S2 | token: `/api/*` without a token or with a wrong one → 401, right token → 200; `index.html` and assets need no token; the token file is created once (mode 0600 on POSIX) and reused; the env override works |
| S3 | Host check: `Host: evil.example` → 400; `127.0.0.1:<port>` and `localhost:<port>` → 200 |
| S4 | browser guards: a cross-origin preflight gets no `Access-Control-Allow-*`; CSP header on `index.html`; `/docs` and `/redoc` → 404 |
| S5 | telemetry: the app's telemetry config is all off; with `FASTAPI_OTEL_AUTO_CONFIGURE=true` and `OTEL_EXPORTER_OTLP_ENDPOINT` set, requests still succeed and nothing is exported |
| S6 | scan: recursion; skip rules (`_x.py`, `.hidden/`, `__pycache__`, a venv with `pyvenv.cfg`, `node_modules`); case-insensitive sort; ids stable and unique; POSIX paths on Windows |
| S7 | sidecar: every status; malformed JSON → `unknown` with a reason; stale by sha256; missing folder → `workspace_missing` |
| S8 | 50 scripts with sidecars scan in < 100 ms; 5 001 scripts → `truncated` |
| S9 | settings: defaults; PUT round trip persisted except `workspace`; bad enum → 422; missing folder → 422 field error; corrupted file → defaults plus a warning; atomic write |
| S10 | system: fake probe output parsed; no CuPy → `[]` and `"missing"`; probe timeout → error string; the probe script never imports etalon |
| S11 | SPA fallback: `/settings` and `/sim/x/setup` → `index.html` with `data-theme` and `lang` from the settings; `/api/nope` → 404 JSON; unbuilt SPA → developer page |
| S12 | CLI: `--help`; missing folder → exit 2; busy port → exit 2 with the message; prints the URL with token; `--no-browser` never calls `webbrowser` |
| S13 | OpenAPI: the generated schema equals the committed `studio/src/api/openapi.json` |
| S14 | import weight: `import etalon.studio.server` loads no scipy, xarray, matplotlib or cupy (passes only with D1) |

**vitest**: `studio/src/**/*.test.ts(x)`, jsdom.

| ID | Test |
| --- | --- |
| V1 | catalogs: en and zh-CN have the same keys, no empty values and the same `{{placeholders}}`; zh-CN values differ from en except an explicit allowlist |
| V2 | every `t("…")` key used in `src/` exists in en (static scan) |
| V3 | tokens: every text token reaches ≥ 4.5:1 on bg, surface and raised, and every control token ≥ 3:1, in both themes |
| V4 | components: role and accessible name; keyboard (Segmented arrows, Toggle space, Select open/choose/escape, Button Enter); disabled state; focus ring present |
| V5 | formatters: SI prefixes (42.3 M, 3.1 GB), 4 significant figures, durations (`3m12`, `~2m`, `1h04m`), relative dates in en and zh-CN |
| V6 | API client: the token moves from the URL to `localStorage` and the URL is cleaned; the header is sent; 401 → session ended |
| V7 | Workspace: loading, empty, error with retry, content; the target route for each status; the filter; the no-GPU banner doesn't block; the truncation banner |
| V8 | Settings: loading and error; each control sends the right PUT body; a failure rolls back and shows the error inline; switching language re-renders in zh-CN; `data-theme` follows the setting, and "system" follows `matchMedia` |
| V9 | `schema.ts` regenerated from `openapi.json` equals the committed file |

**Playwright**: `studio/e2e/`, Chromium. It runs against the built SPA served by `etalon studio` on a fixture workspace. Two guards run for every test: any request to a host other than `127.0.0.1:<port>` fails the test, and so does any console error.

| ID | Route | Test |
| --- | --- | --- |
| P1 | `/` | fixture workspace: every status shows its glyph and label, the stale tag shows, skipped files are absent |
| P2 | `/` | generated 50-script workspace: the count says 50, the last row is reachable by scrolling, and clicking a row lands on the route for its status |
| P3 | `/` | open time: spawn the CLI → 50 rows visible in < 2 s |
| P4 | all | language: switch to 简体中文 in Settings; on every route no visible text outside `translate="no"` contains `[A-Za-z]`; the choice survives a reload; switch back |
| P5 | all | theme: dark by default; Light → `html[data-theme=light]` with the paper background, surviving a reload; System follows the emulated colour scheme |
| P6 | `/settings` | every section renders; the backend Select lists the detected devices (or CPU only); changing the folder to a second fixture changes the Workspace; an invalid folder shows an inline error |
| P7 | `/sim/:id/{setup,run,results}`, `/modes`, `/validation`, `/nope` | each not-yet route shows its state; an unknown id shows not-found; `/nope` shows 404 |
| P8 | `/` | a fresh browser context without a token shows the session-ended screen with the reopen instruction |
| P9 | `/` | keyboard: Tab reaches the navigation, the filter and the rows; Enter on a row navigates; the focus ring is visible |

Linters and type checks: ruff; mypy strict on `etalon/studio` as well as `core/`; ESLint (no `any`, no literal UI strings, React hooks rules); `tsc --noEmit`.

## 7. Dependencies and licences

These are the additions to `THIRD_PARTY.md`. Versions were resolved on 2026-10-16 in scratch environments, and the licences read from each package's metadata (`importlib.metadata` for Python, `pnpm licenses list` for JS). The lock files pin these versions, and the check reruns whenever a lock file changes.

### Python, runtime (D5)

| Package | Version | License | Pulled in by |
| --- | --- | --- | --- |
| fastapi | 0.143.2 | MIT | etalon (Studio server) |
| starlette | 1.8.0 | BSD-3-Clause | fastapi |
| uvicorn | 0.54.0 | BSD-3-Clause | etalon (Studio server) |
| anyio | 4.15.1 | MIT | starlette |
| idna | 3.20 | BSD-3-Clause | anyio |
| click | 8.5.0 | BSD-3-Clause | uvicorn |
| h11 | 0.16.0 | MIT | uvicorn |
| annotated-doc | 0.0.5 | MIT | fastapi |
| opentelemetry-api | 1.45.1 | Apache-2.0 | fastapi: the API only, with no SDK or exporter installed; switched off in code (D2) |

pydantic, pydantic-core, typing-extensions, typing-inspection and annotated-types are already listed.

### Python, development only

| Package | Version | License | Notes |
| --- | --- | --- | --- |
| httpx | 0.28.1 | BSD-3-Clause | FastAPI's `TestClient` |
| httpcore | 1.0.9 | BSD-3-Clause | httpx |
| certifi | 2026.7.22 | **MPL-2.0** | httpx; never imported by etalon, never shipped (D4) |

### JS, shipped: bundled into `etalon/studio/static`

| Package | Version | License |
| --- | --- | --- |
| react, react-dom | 19.3.1 | MIT |
| react-router | 7.18.4 | MIT |
| @tanstack/react-query | 5.104.3 | MIT |
| @tanstack/react-virtual | 3.14.20 | MIT |
| i18next | 26.4.5 | MIT |
| react-i18next | 17.0.17 | MIT |
| openapi-fetch | 0.17.0 | MIT |
| @radix-ui/react-select, -switch, -toggle-group, -slot | 2.4.1, 1.4.1, 1.2.1, 1.5.0 | MIT |
| lucide-react | 1.57.0 | ISC (named in spec §7) |
| @fontsource-variable/inter | 5.3.0 | **OFL-1.1** font files (D3) |
| @fontsource-variable/jetbrains-mono | 5.3.0 | **OFL-1.1** font files (D3) |

These pull in 49 more packages, all MIT except one:

- 26 internal `@radix-ui/*` packages
- `@floating-ui/{core,dom,react-dom,utils}`
- react-remove-scroll, react-remove-scroll-bar, react-style-singleton, use-callback-ref, use-sidecar, aria-hidden, get-nonce, detect-node-es
- scheduler, use-sync-external-store
- @tanstack/query-core, @tanstack/virtual-core
- html-parse-stringify, @babel/runtime
- openapi-typescript-helpers
- cookie, set-cookie-parser
- csstype
- **tslib: 0BSD**, the one exception

So the shipped licences are MIT, ISC, 0BSD and OFL-1.1.

### JS, build and test only: never shipped

| Package | Version | License |
| --- | --- | --- |
| typescript | 5.9.3 | Apache-2.0 (pinned, D14) |
| vite | 8.3.4 | MIT |
| @vitejs/plugin-react | 6.1.2 | MIT |
| tailwindcss, @tailwindcss/vite | 4.3.3 | MIT |
| vitest | 5.0.5 | MIT |
| jsdom | 30.1.3 | MIT |
| @testing-library/react, /dom, /user-event, /jest-dom | 16.3.3, 10.4.2, 14.6.8, 7.0.1 | MIT |
| @playwright/test | 1.64.1 | Apache-2.0 |
| openapi-typescript | 7.13.0 | MIT |
| eslint, @eslint/js | 10.12.0, 10.0.1 | MIT |
| typescript-eslint | 8.71.2 | MIT |
| eslint-plugin-react-hooks | 7.1.1 | MIT |
| eslint-plugin-i18next | 6.1.5 | ISC |
| globals | 17.13.0 | MIT |
| @types/react, @types/react-dom, @types/node | 19.3.0, 19.3.0, 26.6.5 | MIT |

About 250 more packages come in transitively. They are MIT, ISC, Apache-2.0 or BSD, except these (D4):

| Package | License | Why it is there |
| --- | --- | --- |
| lightningcss | MPL-2.0 | Tailwind v4 and Vite's CSS engine. It runs at build time; its code is not in the output. |
| caniuse-lite | CC-BY-4.0 | browser-support data for Babel's browserslist, used at build time |
| mdn-data | CC0-1.0 | CSS data used by jsdom |
| type-fest | MIT OR CC0-1.0 | types only |
| lru-cache 11, minimatch 10 | BlueOak-1.0.0 | permissive, used by test tooling |
| argparse | Python-2.0 (PSF) | js-yaml, used by openapi-typescript |
| @csstools/* (2) | MIT-0 | jsdom |

openapi-typescript's Redocly core contains a registry client. It is only used for remote `$ref`s or a Redocly login, and our input is a local file.

## 8. Decisions for review

Each one has a recommendation; say "OK" to take them all.

1. **Lazy `etalon.analysis`.** `import etalon` takes about 12 s on this machine. Of that, 9.4 s is SciPy, which `etalon/__init__.py` pulls in eagerly through `analysis/dispersion.py`. Studio's CLI and server import the package, so "opens in < 2 s" cannot pass as things stand. (Measured with the CPU at 100 % from other sessions, so the absolute numbers are inflated; the share is what matters.) Recommendation: this session loads `analysis` lazily with a PEP 562 `__getattr__`, in a separate commit with a test that `import etalon` loads no SciPy. That is about 15 lines in the package root, no change under `fdtd/`, `grid/`, `analysis/` or `validation/`, and the public API is unchanged (`et.analysis.…` still works). The alternative is to hand this to the solver session in M1. If the rest of the import (NumPy and pydantic for `core`) still breaks the budget on an idle machine, I'll report the numbers rather than make every name lazy.
2. **FastAPI's built-in OpenTelemetry.** Recommendation: keep the current FastAPI, switch telemetry off in code and test that (S5). The alternative, pinning an old FastAPI that predates it, would cost security fixes.
3. **Fonts under OFL-1.1.** Inter and JetBrains Mono are named in CLAUDE.md, but OFL isn't on the MIT/BSD/Apache/PSF list. Recommendation: accept them for these two fonts and ship both OFL texts in `static/licenses/`. OFL allows bundling with software as long as the licence travels with the fonts. The alternative is system fonts only.
4. **Other licences outside the list.** Recommendation: accept them. ISC is shipped (Lucide, already allowed by spec §7–8) and so is 0BSD (tslib). These are build- or test-only, like pathspec today: certifi and lightningcss (MPL-2.0), caniuse-lite (CC-BY-4.0, data), and the BlueOak, CC0 and MIT-0 packages.
5. **Studio's dependencies are core dependencies.** With fastapi and uvicorn in the core install, `pip install etalon` then `etalon studio` just works. That adds 9 small pure-Python packages. The alternative is an `etalon[studio]` extra.
6. **Launch and settings.**
   - (a) The workspace is `etalon studio [FOLDER]`, defaulting to the current directory. It can be switched in Settings while Studio runs, but isn't remembered.
   - (b) The token persists in the config directory. Bookmarks and pasted deep links then keep working across restarts, and `?token=` is needed once per browser.
   - (c) Language gets a "System" option, and it is the default. A Chinese browser opens in Chinese the first time.
   - (d) Settings live in the per-user config directory (§4.3).
7. **Simulation id** = 12 hex characters of sha256 of the relative path. The alternative is a readable slug of the path, which risks collisions and needs escaping for subfolders.
8. **Sidecar.** Recommendation: a per-folder `.etalon/<script name>/status.json`, so results travel with a copied folder and one `.etalon/` line in `.gitignore` covers all depths. Stale is decided by content hash. U2 writes it. The alternative is a single `.etalon/` at the workspace root.
9. **Navigation.** Mode Solver and Validation stay hidden until U4. Their routes exist and say "not in this version yet".
10. **No "New from template" in U0.** The five device templates need PolySlab and ModeSource from M1, and Setup doesn't exist yet. It arrives with U1, and until then the empty state explains how to add scripts.
11. **New endpoint `GET /api/system`** (versions and GPU devices), added to `ui-ux-spec.md` §9. It keeps slow GPU detection off the settings request.
12. **Colour fixes for AA** (§5.4):
    - Dark muted `#6B7380` → `#858D9A`.
    - Dark error `#E5484D` → `#EC5D62`.
    - Light accent is a fill only; accent-coloured text uses `#7A5A12`.
    - Spec §7 gives accent and warn the same hex. I'd keep it: status always carries a glyph and a word, so there's no ambiguity.
13. **Crosshair cursor** only over canvases and the viewport (U1+).
14. **Tooling.**
    - ESLint (typescript-eslint, react-hooks, i18next plugin) enforces no `any` and no literal UI strings.
    - TypeScript is pinned to 5.9, because typescript-eslint (< 6.1) and openapi-typescript (^5) don't accept 6 or 7 yet.
    - Vite builds straight into `etalon/studio/static/` instead of `studio/dist` plus a copy at wheel time (spec §8), so a development install serves the same files.
    - A hatch build hook refuses a wheel without the SPA.
15. **Playwright's browser.** Recommendation: its own Chromium, a one-time download of about 170 MB (`pnpm exec playwright install chromium`), so runs match CI. The alternative is the installed Edge (`channel: "msedge"`): no download, but Windows only.
16. **CSP and no FastAPI docs** (§4.2). With these, the browser itself enforces "no runtime fetches", in addition to the Playwright guard.

## 9. Order of work (one small commit each)

1. Docs: this plan with its outcome, the `ui-ux-spec.md` §7 and §9 updates, and `docs/design/README.md` with the decisions.
2. D1: lazy `analysis` plus its import test (if OK'd).
3. Python: settings, security, workspace, system, server, CLI; dependencies in `pyproject.toml` and `uv.lock`; `openapi.json`; S1–S14.
4. `studio/` scaffold: Vite, TypeScript, Tailwind and the tokens, fonts, ESLint, vitest, API generation, i18n; V1–V3, V9.
5. Components; V4–V5.
6. Shell, routes, Workspace and Settings; V6–V8.
7. Playwright fixtures and P1–P9.
8. `THIRD_PARTY.md`, the README Studio section and the hatch hook; the full check (pytest, vitest, Playwright, ruff, mypy, ESLint, tsc); the measured open time recorded in §10 of this plan.

## 10. Risks

- **Import time** (D1). This machine was at 100 % CPU during planning. P3 is measured idle, and I'll report the number, not just pass/fail.
- **pnpm 10** blocks dependency install scripts by default. Vite 8 (rolldown), lightningcss and Tailwind's oxide ship native binaries as optional dependencies, without scripts. I'll confirm the build works with no scripts allowed.
- **Windows paths:** backslashes, case-insensitive sorting, long paths. Ids and API paths use POSIX separators, and the UI shows the native path.
- **zh-CN quality:** written by me and checked by V1, P4 and a native speaker in U4.
