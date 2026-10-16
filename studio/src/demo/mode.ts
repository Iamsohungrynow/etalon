/**
 * The static demo build (docs/plan-demo.md): `pnpm build:demo` builds with
 * VITE_ETALON_DEMO=1 (studio/.env.demo). Vite replaces the flag at build time, so in
 * the regular build the demo adapter is dead code and is dropped.
 */
export const DEMO = import.meta.env.VITE_ETALON_DEMO === "1";

/** Where the demo build serves the recorded answers (studio/demo-data/). */
export const DEMO_DATA_BASE = "/demo-data/";
