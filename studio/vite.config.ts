/// <reference types="vitest/config" />
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

/**
 * Ship the fonts' OFL-1.1 texts and THIRD_PARTY.md next to the bundle (plan-u0 D3):
 * OFL allows bundling the fonts as long as the licence travels with them.
 */
function licences(): Plugin {
  const files: Record<string, string> = {
    "licenses/inter-OFL.txt": "node_modules/@fontsource-variable/inter/LICENSE",
    "licenses/jetbrains-mono-OFL.txt": "node_modules/@fontsource-variable/jetbrains-mono/LICENSE",
    "licenses/THIRD_PARTY.md": "../THIRD_PARTY.md",
  };
  return {
    name: "etalon-licences",
    apply: "build",
    generateBundle() {
      for (const [fileName, source] of Object.entries(files)) {
        this.emitFile({ type: "asset", fileName, source: readFileSync(here(source)) });
      }
    },
  };
}

/**
 * The demo build (`pnpm build:demo`, docs/plan-demo.md) ships the recorded answers in
 * studio/demo-data/ (studio/scripts/record_demo.py) at /demo-data/.
 */
function demoData(): Plugin {
  const root = here("demo-data");
  return {
    name: "etalon-demo-data",
    apply: "build",
    buildStart() {
      if (!existsSync(`${root}/manifest.json`)) {
        this.error("studio/demo-data/ is empty: run studio/scripts/record_demo.py first");
      }
    },
    generateBundle() {
      for (const name of readdirSync(root, { recursive: true, encoding: "utf-8" })) {
        const path = `${root}/${name.replaceAll("\\", "/")}`;
        if (!name.endsWith(".json") && !name.endsWith(".bin")) continue;
        this.emitFile({
          type: "asset",
          fileName: `demo-data/${name.replaceAll("\\", "/")}`,
          source: readFileSync(path),
        });
      }
    },
  };
}

export default defineConfig(({ mode }) => ({
  // ETALON_BASE=/studio/ serves the demo under a sub-path (the landing page owns /).
  base: process.env.ETALON_BASE ?? "/",
  plugins: [react(), tailwindcss(), licences(), ...(mode === "demo" ? [demoData()] : [])],
  build: {
    // Served by etalon/studio/server.py and shipped in the wheel (gitignored); the demo
    // build goes to studio/dist-demo/ for Netlify (netlify.toml).
    outDir: mode === "demo" ? here("dist-demo") : here("../etalon/studio/static"),
    emptyOutDir: true,
    modulePreload: { polyfill: false }, // no inline script, so the CSP can stay script-src 'self'
    assetsInlineLimit: 0, // no data: fonts either, so the CSP can stay font-src 'self'
    chunkSizeWarningLimit: 1024,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // `etalon studio --no-browser` in another terminal, then open
    // http://127.0.0.1:5173/?token=<token it printed>.
    proxy: { "/api": { target: "http://127.0.0.1:8787", changeOrigin: true, ws: true } },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
    css: false,
  },
  preview: {
    host: "127.0.0.1",
    port: 8792,
    strictPort: true,
  },
}));
