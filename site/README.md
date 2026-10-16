# etalon landing page

Static page in the visual language of `docs/design/studio-reference.html`, deployed at https://etalon-studio.netlify.app. Every field, curve and log line on it comes from `data.json`, which `build_data.py` writes from real etalon runs on the GPU:

```bash
.venv/Scripts/python site/build_data.py
```

To deploy:
1. Copy `bench/results/m0_vacuum.png` into `site/`.
2. Publish the folder (without `build_data.py` and this README) with `netlify deploy --no-build --dir <folder> --site <id>`, run from a directory that has no `netlify.toml`.

`_headers` carries the same CSP as Studio, so nothing loads from another origin. Fonts are bundled, under the SIL OFL 1.1 (`fonts/OFL-*.txt`).
