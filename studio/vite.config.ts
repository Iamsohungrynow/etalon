/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
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

export default defineConfig({
  plugins: [react(), tailwindcss(), licences()],
  build: {
    // Served by etalon/studio/server.py and shipped in the wheel (gitignored).
    outDir: here("../etalon/studio/static"),
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
    proxy: { "/api": { target: "http://127.0.0.1:8787", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
    css: false,
  },
});
