# Studio static demo (Netlify) — short plan and outcome

Asked for on 2026-10-16: a demo of Studio that replays recorded results, with no backend and no GPU, for Netlify (`etalon-netlify`). Studio itself still binds 127.0.0.1 only; the demo is a separate static build.

## Design

1. **Recorded, never made up.** `studio/scripts/record_demo.py` starts Studio's own server in-process (FastAPI TestClient, no port) on a fresh workspace. It then:
   - creates the four templates through `POST /api/simulations`;
   - runs each through `POST /api/simulations/{id}/run` on the GPU, recording every WebSocket frame with its arrival time;
   - makes every GET the UI can make and stores the answers byte for byte in `studio/demo-data/`, with a `manifest.json` keyed by request (`GET /api/x?a=1&b=2`, query sorted).

   Local paths are rewritten (`~/etalon-demo`), and the script fails if any remain. Live frames are thinned to at most 90 per run.
2. **A build mode, not a fork.** `pnpm build:demo` builds with `VITE_ETALON_DEMO=1` (`studio/.env.demo`) into `studio/dist-demo/` and copies `demo-data/` in. Only two seams change:
   - `main.tsx` gives the openapi-fetch client a `fetch` that answers from the recording (`src/demo/staticApi.ts`);
   - `openJobSocket` replays the recorded frames at their recorded times (`src/demo/replaySocket.ts`).

   Every screen, query and generated type is the real one.
3. **What needs the local Studio is disabled.** This covers New from template, Cancel, Calibrate and changing the workspace folder. Each disabled control carries a `demo.needsLocal` tooltip. Anything else that writes answers 503 `demo_static`.

   Settings changes (language, theme, units) stay in the tab's memory. Run replays the recording; while it plays, the workspace row shows it as running, as the real server does.
4. **Banner.** `demo.banner` (en and zh-CN) sits above the header on every screen: recorded results replayed in the browser, and the real Studio runs locally with `etalon studio`.
5. **Netlify.** `netlify.toml` sets base `studio`, `pnpm build:demo`, publish `dist-demo`, and the SPA fallback `/* → /index.html 200`. It also sends the same CSP as the local Studio (`default-src 'self'`), so nothing loads from elsewhere.

   `demo-data/` (28 MB of arrays) is not committed, so the site is built locally and deployed with `netlify deploy --no-build --dir studio/dist-demo`: a draft first, then `--prod`.

## Tests

- **vitest:** `src/demo/staticApi.test.ts` covers request keys, recorded answers and statuses, in-memory settings, the replay's running row and 409, and 503 for writes. It also checks that the replay plays at the recorded times, stops when closed, and reports a missing recording as a lost connection.
- **Playwright** (`pnpm e2e:demo`, against `vite preview` of the demo build): the test fails on any off-site request or console error.
  - The banner shows, with the four rows, and New is disabled.
  - The Setup 3D view draws, and the slice reads εr = 12.08 on the line defect.
  - Run replays to "The run finished." on cuda:0, Cancel is disabled, and Results shows the field and the spectra table.
  - The Chinese banner shows under a zh-CN browser.

## Not done

- No cancelled or failed run is recorded, so the demo shows only the finished outcome.
- The misplaced-strip and broken-script examples are not in the demo workspace.
- The demo data is not in git; rerun the recorder (about 40 s on the GPU) to rebuild it.
