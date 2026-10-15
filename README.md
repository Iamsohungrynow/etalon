# etalon

GPU-accelerated, on-premise photonic FDTD with a Python-native API. It runs on one local NVIDIA GPU, with an identical-result CPU fallback, and your data never leaves your machine. Apache-2.0.

## Status

**M0 done (2026-10-15):** 2D TE FDTD (Ex, Ey, Hz) with CPML, point sources, DFT monitors, a NumPy reference backend and a CUDA backend. Next: M1 (3D, mode solver, S-parameters). Open questions for it are in [`docs/plan-m1.md`](docs/plan-m1.md).

M0 acceptance, measured with `bench/validate_m0.py` (report: [`bench/results/m0_vacuum.png`](bench/results/m0_vacuum.png)):

| Criterion | Required | Measured |
| --- | --- | --- |
| Phase velocity vs the Yee dispersion relation, 0° and 45° | < 0.5 % | ≤ 1.3e-4 at 9–18 cells/λ, ≤ 3.5e-5 at 18–36, ≤ 1.1e-5 at 36–72 |
| CUDA == NumPy | rtol 1e-5 | bit-for-bit identical (float32 and float64) |
| Throughput, 2000 × 2000 grid | ≥ 2e8 cell-updates/s on an RTX 3060-class GPU | 2.9e9 on an RTX 4060 Ti (float32), 1.5e9 (float64) |

Also checked: CPML reflection −91 dB at 12 layers; no late-time growth over 30 000 steps; absolute field vs the analytic 2D Green's function within 0.4 % at 26 cells/λ, converging at second order.

Not yet: 3D, 2D TM, mode solver, S-parameters, subpixel smoothing, nonuniform grids, dispersive media, HDF5 output, Studio.

## Example

```python
import numpy as np
import etalon as et

sim = et.Simulation(
    size=(8.0, 8.0, 0.0),  # µm; size_z = 0 -> 2D TE
    grid=et.UniformGrid(dl=0.05),  # µm
    boundary=et.PML(layers=12),  # CPML, outside `size`
    sources=[
        et.PointSource(
            center=(-3, 0, 0),
            component="Hz",
            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.5),
        )
    ],
    monitors=[et.DFTMonitor(name="probe", center=(3, 0, 0), wavelengths=np.linspace(1.3, 1.8, 26))],
    run_time=300e-15,  # s
    backend="auto",  # "cuda", "numpy" or "auto"
)
print(sim.summary())  # cells, dt, steps, memory: before running
result = sim.run()
hz = result["probe"]["Hz"]  # complex xarray.DataArray over wavelength
```

The full script is [`examples/00_vacuum_pulse.py`](examples/00_vacuum_pulse.py). Units: lengths in µm, time in s, frequency in Hz; time convention exp(−iωt).

## Install (development)

```bash
uv sync --extra gpu
```

The CUDA backend also needs NVIDIA's CUDA headers and NVRTC, from either a CUDA Toolkit install or NVIDIA's pip wheels. etalon does not declare these because of their license (see [`THIRD_PARTY.md`](THIRD_PARTY.md)):

```bash
uv pip install "cupy-cuda12x[ctk]"
```

Without a GPU, everything runs on the NumPy backend and gives the same results.

## Tests

```bash
uv run pytest
```

- `tests/unit`: fast checks on CPU.
- `tests/validation`: physics against analytic results, CPU, about 40 s.
- `tests/gpu`: CUDA vs NumPy equality and throughput; skipped without CuPy.

The full suite takes about a minute.

## Licence

Apache-2.0 ([`LICENSE`](LICENSE)). Third-party licences are listed in [`THIRD_PARTY.md`](THIRD_PARTY.md).
