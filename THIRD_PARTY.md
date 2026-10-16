# Third-party software

etalon is Apache-2.0. Policy (CLAUDE.md): dependencies must be MIT, BSD, Apache or PSF licensed; nothing GPL or LGPL; nothing vendored. Meep (GPL-2.0) is only ever run as an external benchmark in its own environment.

Licenses below come from each package's installed metadata: for Python `License-Expression`, `License` and classifiers, checked against `uv.lock`; for the Studio frontend `pnpm licenses list`, checked against `studio/pnpm-lock.yaml`. Python checked 2026-10-15 (solver) and 2026-10-16 (Studio); JS checked 2026-10-16. Re-run the checks when a lock file changes:

```bash
python -c "from importlib import metadata as m; [print(d.metadata['Name'], d.metadata.get('License-Expression') or d.metadata.get('License','').splitlines()[:1]) for d in m.distributions()]"
pnpm --dir studio licenses list --prod
pnpm --dir studio licenses list
```

## Runtime — declared in `pyproject.toml`

| Package | Version | License | Used for |
| --- | --- | --- | --- |
| numpy | 2.5.4 | BSD-3-Clause (wheel also bundles 0BSD, MIT, Zlib, CC0-1.0 parts) | arrays, the reference backend |
| scipy | 1.18.1 | BSD-3-Clause | Hankel functions, root finding (analysis) |
| pydantic | 2.14.1 | MIT | user-facing models |
| xarray | 2026.9.0 | Apache-2.0 | labelled results |
| matplotlib | 3.11.2 | Matplotlib License (PSF-based) | plots |
| fastapi | 0.143.2 | MIT | Studio server (`etalon studio`) |
| uvicorn | 0.54.0 | BSD-3-Clause | Studio server |
| websockets | 17.2 | BSD-3-Clause | Studio job progress over WebSocket (uvicorn needs it); no dependencies of its own |

## Runtime — pulled in by the above

| Package | License | Pulled in by |
| --- | --- | --- |
| pydantic-core | MIT | pydantic |
| annotated-types | MIT | pydantic |
| typing-extensions | PSF-2.0 | pydantic |
| typing-inspection | MIT | pydantic |
| pandas | BSD-3-Clause | xarray |
| packaging | Apache-2.0 OR BSD-2-Clause | xarray, matplotlib |
| python-dateutil | Apache-2.0 / BSD (dual) | pandas, matplotlib |
| six | MIT | python-dateutil |
| tzdata | Apache-2.0 | pandas |
| contourpy | BSD-3-Clause | matplotlib |
| cycler | BSD-3-Clause | matplotlib |
| fonttools | MIT | matplotlib |
| kiwisolver | BSD-3-Clause | matplotlib |
| pillow | **MIT-CMU** (see below) | matplotlib |
| pyparsing | MIT | matplotlib |
| starlette | BSD-3-Clause | fastapi |
| annotated-doc | MIT | fastapi |
| opentelemetry-api | Apache-2.0 | fastapi: the API only, no SDK or exporter installed; Studio switches FastAPI's telemetry off in code and tests that (`tests/studio/test_security.py`) |
| anyio | MIT | starlette |
| idna | BSD-3-Clause | anyio |
| click | BSD-3-Clause | uvicorn |
| h11 | MIT | uvicorn |

## GPU extra — `etalon[gpu]`

| Package | Version | License |
| --- | --- | --- |
| cupy-cuda12x | 14.2.0 | MIT |
| cuda-pathfinder | 1.8.3 | Apache-2.0 (CuPy dependency) |

## Platform requirement — NVIDIA CUDA (not declared, not distributed)

CuPy compiles etalon's kernels at run time and needs NVIDIA's CUDA headers and NVRTC. They come from the NVIDIA driver plus either a CUDA Toolkit install or NVIDIA's pip wheels (`pip install "cupy-cuda12x[ctk]"`, which brings `cuda-toolkit`, `nvidia-cuda-nvrtc-cu12`, `nvidia-cuda-runtime-cu12`, `nvidia-cublas-cu12`, `nvidia-cufft-cu12`, `nvidia-curand-cu12`, `nvidia-cusolver-cu12`, `nvidia-cusparse-cu12` and `nvidia-nvjitlink-cu12`). All of these are under NVIDIA's proprietary license. Like the GPU driver, they are a platform the user installs. etalon does not declare them in `pyproject.toml` or ship them. They are installed in the development venv only.

## Studio frontend — bundled into `etalon/studio/static` and shipped in the wheel

Built by Vite from `studio/` (pnpm). 76 packages end up in the bundle; the 3D viewport (three.js) and the charts (ECharts) load only with the screens that use them.

| Package | Version | License |
| --- | --- | --- |
| react, react-dom | 19.3.1 | MIT |
| react-router | 7.18.4 | MIT |
| @tanstack/react-query | 5.104.3 | MIT |
| @tanstack/react-virtual | 3.14.20 | MIT |
| i18next | 26.4.5 | MIT |
| react-i18next | 17.0.17 | MIT |
| openapi-fetch | 0.17.0 | MIT |
| @radix-ui/react-select, -switch, -toggle-group, -slot, -tabs | 2.4.1, 1.4.1, 1.2.1, 1.5.0, 1.2.1 | MIT |
| three | 0.186.1 | MIT (Setup's 3D viewport; OrbitControls from its examples) |
| @react-three/fiber | 9.8.2 | MIT |
| echarts | 6.1.0 | Apache-2.0 (tree-shaken: line charts only) |
| zrender | 6.1.0 | BSD-3-Clause (ECharts' renderer) |
| zustand | 5.0.15 | MIT (Setup's selection store) |
| lucide-react | 1.57.0 | **ISC** (see below) |
| @fontsource-variable/inter | 5.3.0 | **OFL-1.1** font files (see below) |
| @fontsource-variable/jetbrains-mono | 5.3.0 | **OFL-1.1** font files (see below) |

Pulled in by the above, all MIT except one:

- 26 internal `@radix-ui/*` packages
- @floating-ui/core, dom, react-dom, utils
- react-remove-scroll, react-remove-scroll-bar, react-style-singleton, use-callback-ref, use-sidecar, aria-hidden, get-nonce, detect-node-es
- scheduler, use-sync-external-store
- @tanstack/query-core, @tanstack/virtual-core
- html-parse-stringify, @babel/runtime
- openapi-typescript-helpers
- cookie, set-cookie-parser
- csstype
- its-fine, react-use-measure, suspend-react (@react-three/fiber)
- buffer, base64-js (MIT) and **ieee754 (BSD-3-Clause)** (three.js tooling pulled in by @react-three/fiber)
- **tslib: 0BSD** (see below)

Colormap data, generated once from matplotlib 3.11.2 by `studio/scripts/gen_colormaps.py` into `studio/src/field/colormaps.ts` (256-entry RGB tables, shipped):

| Colormap | Authors | License |
| --- | --- | --- |
| viridis | Stéfan van der Walt and Nathaniel Smith (with Eric Firing) | CC0-1.0 |
| RdBu | Cynthia Brewer, Mark Harrower and The Pennsylvania State University (ColorBrewer) | Apache-2.0 |

The fonts' OFL texts ship with the bundle as `static/licenses/inter-OFL.txt` and `static/licenses/jetbrains-mono-OFL.txt`, together with this file as `static/licenses/THIRD_PARTY.md`. Studio's Settings → About links to all three.

## Studio frontend — build and test only, never shipped

| Package | Version | License |
| --- | --- | --- |
| typescript | 5.9.3 | Apache-2.0 (pinned below 6: typescript-eslint and openapi-typescript do not accept 6 or 7 yet) |
| vite | 8.3.4 | MIT |
| @vitejs/plugin-react | 6.1.2 | MIT |
| tailwindcss, @tailwindcss/vite | 4.3.3 | MIT |
| vitest | 5.0.5 | MIT |
| jsdom | 30.1.3 | MIT |
| @testing-library/react, dom, user-event, jest-dom | 16.3.3, 10.4.2, 14.6.8, 7.0.1 | MIT |
| @playwright/test | 1.64.1 | Apache-2.0 (its Chromium download is for tests on the developer's machine only) |
| openapi-typescript | 7.13.0 | MIT |
| eslint, @eslint/js | 10.12.0, 10.0.1 | MIT |
| typescript-eslint | 8.71.2 | MIT |
| eslint-plugin-react-hooks | 7.1.1 | MIT |
| eslint-plugin-i18next | 6.1.5 | ISC |
| globals | 17.13.0 | MIT |
| @types/react, @types/react-dom, @types/node, @types/three | 19.3.0, 19.3.0, 26.6.5, 0.186.0 | MIT |

About 230 more packages come in transitively: MIT, ISC, Apache-2.0, BSD-2-Clause or BSD-3-Clause, except these:

| Package | License | Why it is there |
| --- | --- | --- |
| lightningcss | MPL-2.0 | Tailwind v4 and Vite's CSS engine; runs at build time, its code is not in the output |
| caniuse-lite | CC-BY-4.0 | browser-support data for Babel's browserslist, build time |
| mdn-data | CC0-1.0 | CSS data used by jsdom |
| type-fest | MIT OR CC0-1.0 | types only |
| lru-cache 11, minimatch 10 | BlueOak-1.0.0 | test tooling |
| argparse | Python-2.0 (PSF) | js-yaml, used by openapi-typescript |
| @csstools/color-helpers, css-syntax-patches-for-csstree | MIT-0 | jsdom |

## Development only — not shipped

| Package | License | Notes |
| --- | --- | --- |
| pytest, iniconfig, pluggy | MIT | |
| httpx2, httpcore2 | BSD-3-Clause | the test client Starlette 1.8 asks for |
| truststore | MIT | httpx2 |
| colorama | BSD-3-Clause | pytest on Windows |
| pygments | BSD-2-Clause | pytest |
| ruff | MIT | |
| mypy, mypy-extensions, librt, ast-serialize | MIT | |
| pathspec | **MPL-2.0** | mypy dependency (see below) |
| hatchling | MIT | build backend |
| uv | MIT OR Apache-2.0 | environment manager |

## Outside the MIT / BSD / Apache / PSF list — needs a decision

1. **pillow (MIT-CMU)**: a permissive, OSI-approved "historical permission notice" license with no copyleft. It is a hard runtime dependency of matplotlib. Options: accept MIT-CMU as permissive, or move matplotlib to an optional `etalon[plot]` extra.
2. **numpy's bundled 0BSD / Zlib / CC0-1.0 parts**: all permissive, no copyleft. Recommend accepting.
3. **pathspec (MPL-2.0)**: file-level weak copyleft. It is used only by the mypy dev tool, never imported by etalon and never distributed. Recommend accepting for development only.
4. **NVIDIA CUDA runtime**: proprietary, handled as a platform requirement above.

Accepted for Studio on 2026-10-16 (`docs/plan-u0.md` §8, D3 and D4):

5. **Inter and JetBrains Mono fonts (OFL-1.1)**: CLAUDE.md names both fonts. OFL lets software bundle the fonts provided the license travels with them, which it does (`static/licenses/`).
6. **lucide-react (ISC)** and **tslib (0BSD)**: shipped. Both are permissive; spec §7–8 already allows ISC.
7. **lightningcss (MPL-2.0), caniuse-lite (CC-BY-4.0), mdn-data and type-fest (CC0-1.0), lru-cache and minimatch (BlueOak-1.0.0), @csstools (MIT-0)**: build and test tools only, never shipped, like pathspec.
8. **viridis (CC0-1.0)**: the colormap's numbers, shipped as data. Public-domain dedication; accepted with U1 (`docs/plan-u1.md`), like numpy's CC0 parts.
