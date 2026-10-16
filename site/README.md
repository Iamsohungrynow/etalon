# etalon landing page

Static page in the visual language of `docs/design/studio-reference.html`, deployed at https://etalon-studio.netlify.app. Every field, curve and log line on it comes from `data.json`, which `build_data.py` writes from real etalon runs on the GPU:

```bash
.venv/Scripts/python site/build_data.py
```

The Studio demo is served from the same site under `/studio/`: build it with `ETALON_BASE=/studio/ pnpm build:demo` (from PowerShell; Git Bash rewrites the leading slash into a Windows path) and copy `studio/dist-demo/` to `studio/` in the publish folder. `_redirects` sends its routes to its `index.html`.

To deploy:
1. Copy `bench/results/m0_vacuum.png` into `site/`.
2. Publish the folder (without `build_data.py` and this README) with `netlify deploy --no-build --dir <folder> --site <id>`, run from a directory that has no `netlify.toml`.

`_headers` carries the same CSP as Studio, so nothing loads from another origin. Fonts are bundled, under the SIL OFL 1.1 (`fonts/OFL-*.txt`).
