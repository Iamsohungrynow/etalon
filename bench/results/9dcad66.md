# etalon vs Meep — 9dcad66

Generated 2026-10-16T13:52:16+00:00 by `python -m bench.report`.
Plan and gates: `docs/plan-bench.md` §8; numbers: `bench/config.yaml`.

- **Meep** 1.35.0, 6 MPI ranks, double precision, on AMD Ryzen 5 5600 6-Core Processor (Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39)
- **etalon** 0.0.1, single precision; GPU: cuda:0 NVIDIA GeForce RTX 4060 Ti; CPU: NumPy reference backend, one thread

## Tier 2d: 2D, resolution 50 px/µm (Δ = 20 nm), PML 1.0 µm, Meep S = 0.5 (etalon courant 0.7071)

2D effective-index model: core n = 2.84778, cladding 1.444.

| Device | Compared | Gate | Max Δ | Pass | Max \|ΔS\| | etalon GPU | etalon CPU | Meep CPU | Resolution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| point2d | T21 = Hz(probe 2) / Hz(probe 1), complex | 0.0010 | 2.14e-06 | ✓ | 2.13e-06 | 4.4 s | 14.6 s | 2.6 s | 50 |
| straight | needs M1: ModeSource, ModePortMonitor, PolySlab (not in etalon 0.0.1 yet) | — | — | — | — | unsupported | unsupported | 8.2 s | 50 |
| bend | needs M1: ModeSource, ModePortMonitor, PolySlab (not in etalon 0.0.1 yet) | — | — | — | — | unsupported | unsupported | 45.3 s | 50 |
| dc | needs M1: ModeSource, ModePortMonitor, PolySlab (not in etalon 0.0.1 yet) | — | — | — | — | unsupported | unsupported | 6.4 min | 50 |
| mmi | needs M1: ModeSource, ModePortMonitor, PolySlab (not in etalon 0.0.1 yet) | — | — | — | — | unsupported | unsupported | 6.4 min | 50 |
| ring | needs M1: ModeSource, ModePortMonitor, PolySlab (not in etalon 0.0.1 yet) | — | — | — | — | unsupported | unsupported | 2.6 h | 50 |

### 2d · point2d

| Metric | Value | Gate | Pass |
| --- | --- | --- | --- |
| max \|ΔT21\| (complex) | 2.14e-06 | 0.0010 | ✓ |

Compared against etalon's cuda run.
NumPy run vs Meep: worst gated metric 2.34e-06.
CUDA vs NumPy: max |ΔS| = 4.27e-07.

- meep meep-mpi: 1.5e+05 cells (500 × 300), 8994 steps, wall 2.6 s, stepping 1.9 s, 7.00e+08 cell-updates/s, final decay 2.2e-10
- etalon cuda: 1.5e+05 cells (500 × 300), 8994 steps, wall 4.4 s, stepping 4.3 s, 3.17e+08 cell-updates/s
- etalon numpy: 1.5e+05 cells (500 × 300), 8994 steps, wall 14.6 s, stepping 14.6 s, 9.22e+07 cell-updates/s

### 2d · straight

Meep reference at λ = 1.5500 µm: |S11|² = 0.0000, |S21|² = 1.0000.

- meep meep-mpi: 2.1e+05 cells (700 × 300), 29979 steps, wall 8.2 s, stepping 7.9 s, 7.95e+08 cell-updates/s, final decay 6.5e-16

### 2d · bend

Meep reference at λ = 1.5500 µm: |S11|² = 0.0000, |S21|² = 0.9936.

- meep meep-mpi: 2.7e+05 cells (520 × 520), 29979 steps, wall 45.3 s, stepping 11.8 s, 6.85e+08 cell-updates/s, final decay 1.2e-16

### 2d · dc

Meep reference at λ = 1.5500 µm: |S11|² = 0.0000, |S21|² = 0.0000, |S31|² = 0.2921, |S41|² = 0.7065.

- meep meep-mpi: 9.89e+05 cells (2300 × 430), 47967 steps, wall 6.4 min, stepping 3.8 min, 2.11e+08 cell-updates/s, final decay 1.2e-13

### 2d · mmi

Meep reference at λ = 1.5500 µm: |S11|² = 0.0001, |S21|² = 0.4492, |S31|² = 0.4491.

- meep meep-mpi: 1.24e+06 cells (2480 × 500), 59958 steps, wall 6.4 min, stepping 6.3 min, 1.98e+08 cell-updates/s, final decay 5.5e-09

### 2d · ring

Meep reference at λ = 1.5500 µm: |S11|² = 0.0000, |S21|² = 0.0751, |S31|² = 0.8692, |S41|² = 0.0000.
Meep resonances: λ 1.53958 µm, Q 2587, ER 24.9 dB; λ 1.55009 µm, Q 2426, ER 30.8 dB; λ 1.56074 µm, Q 2266, ER 27.1 dB; FSR 10.58 nm.

- meep meep-mpi: 2e+06 cells (1500 × 1330), 719502 steps, wall 2.6 h, stepping 2.4 h, 1.63e+08 cell-updates/s, final decay 1.1e-06
