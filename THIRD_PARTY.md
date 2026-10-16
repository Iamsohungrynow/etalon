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

## Benchmark harness — `bench` dependency group (not an etalon dependency)

Installed by `uv sync` for development; never required by `import etalon`.

| Package | Version | License | Used for |
| --- | --- | --- | --- |
| pyyaml | 6.0.3 | MIT (classifier; checked on PyPI and in installed metadata, 2026-10-16) | reading `bench/config.yaml` |

## External benchmark — Meep (not a dependency, never imported by etalon)

The bench compares etalon against [Meep](https://meep.readthedocs.io/), which is **GPL-2.0-or-later**. Meep is an external reference program, not a dependency.
- It lives only in its own conda environment, `bench/meep/env.yaml`, with every package pinned in `bench/meep/env.lock.txt`. On Windows that environment is inside WSL2.
- It runs only as a subprocess started by `bench/run_meep_comparison.py`.
- Only the scripts in `bench/meep/` import it. Nothing in etalon or in the rest of `bench/` does, and `tests/bench/test_import_guard.py` enforces that.
- etalon distributes none of it.
- Meep's output, the S-parameter JSON in `bench/meep/out/`, is data produced by the program and is not covered by its license.

The Meep environment, as installed on 2026-10-16. Licenses are from the conda package metadata:

| Package | Version | License |
| --- | --- | --- |
| pymeep (Meep) | 1.35.0 (mpi_mpich build) | GPL-2.0-or-later |
| mpb | 1.12.0 | GPL-2.0-or-later |
| harminv | 1.4.3 | GPL-2.0-or-later |
| libctl | 4.7.1 | GPL-2.0-or-later |
| libgdsii | 0.21 | GPL-2.0-or-later |
| fftw | 3.3.10 | GPL-2.0-or-later |
| gsl | 2.8 | GPL-3.0-or-later |
| mpich | 4.3.2 | MPICH license (permissive) |
| mpi4py, numpy, scipy, h5py, hdf5, libopenblas | see `env.lock.txt` | BSD-3-Clause |
| pyyaml, pydantic | 6.0.3, 2.14.1 | MIT |
| python | 3.12.15 | PSF (Python-2.0) |

Tools that set the environment up: micromamba (BSD-3-Clause) inside the WSL2 Ubuntu 24.04 distribution.

## Outside the MIT / BSD / Apache / PSF list — needs a decision

1. **pillow (MIT-CMU)**: a permissive, OSI-approved "historical permission notice" license with no copyleft. It is a hard runtime dependency of matplotlib. Options: accept MIT-CMU as permissive, or move matplotlib to an optional `etalon[plot]` extra.
2. **numpy's bundled 0BSD / Zlib / CC0-1.0 parts**: all permissive, no copyleft. Recommend accepting.
3. **pathspec (MPL-2.0)**: file-level weak copyleft. It is used only by the mypy dev tool, never imported by etalon and never distributed. Recommend accepting for development only.
4. **NVIDIA CUDA runtime**: proprietary, handled as a platform requirement above.
