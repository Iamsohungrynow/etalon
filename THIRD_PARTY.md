# Third-party software

etalon is Apache-2.0. Policy (CLAUDE.md): dependencies must be MIT, BSD, Apache or PSF licensed; nothing GPL or LGPL; nothing vendored. Meep (GPL-2.0) is only ever run as an external benchmark in its own environment.

Licenses below come from each package's installed metadata (`License-Expression`, `License`, classifiers), checked on 2026-10-15 against the versions in `uv.lock`. Re-run the check when `uv.lock` changes:

```bash
python -c "from importlib import metadata as m; [print(d.metadata['Name'], d.metadata.get('License-Expression') or d.metadata.get('License','').splitlines()[:1]) for d in m.distributions()]"
```

## Runtime — declared in `pyproject.toml`

| Package | Version | License | Used for |
| --- | --- | --- | --- |
| numpy | 2.5.4 | BSD-3-Clause (wheel also bundles 0BSD, MIT, Zlib, CC0-1.0 parts) | arrays, the reference backend |
| scipy | 1.18.1 | BSD-3-Clause | Hankel functions, root finding (analysis) |
| pydantic | 2.14.1 | MIT | user-facing models |
| xarray | 2026.9.0 | Apache-2.0 | labelled results |
| matplotlib | 3.11.2 | Matplotlib License (PSF-based) | plots |

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

## GPU extra — `etalon[gpu]`

| Package | Version | License |
| --- | --- | --- |
| cupy-cuda12x | 14.2.0 | MIT |
| cuda-pathfinder | 1.8.3 | Apache-2.0 (CuPy dependency) |

## Platform requirement — NVIDIA CUDA (not declared, not distributed)

CuPy compiles etalon's kernels at run time and needs NVIDIA's CUDA headers and NVRTC. They come from the NVIDIA driver plus either a CUDA Toolkit install or NVIDIA's pip wheels (`pip install "cupy-cuda12x[ctk]"`, which brings `cuda-toolkit`, `nvidia-cuda-nvrtc-cu12`, `nvidia-cuda-runtime-cu12`, `nvidia-cublas-cu12`, `nvidia-cufft-cu12`, `nvidia-curand-cu12`, `nvidia-cusolver-cu12`, `nvidia-cusparse-cu12` and `nvidia-nvjitlink-cu12`). All of these are under NVIDIA's proprietary license. Like the GPU driver, they are a platform the user installs. etalon does not declare them in `pyproject.toml` or ship them. They are installed in the development venv only.

## Development only — not shipped

| Package | License | Notes |
| --- | --- | --- |
| pytest, iniconfig, pluggy | MIT | |
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
