"""Vacuum pulse: the first rung of the validation ladder.

A magnetic point dipole (Hz) launches a broadband pulse into 2D free space.
Two point monitors on the x axis record the spectrum of Hz; the phase that
accumulates between them gives the phase velocity of light *on the grid*.
It differs from c by the Yee scheme's numerical dispersion, which is known in
closed form (Taflove & Hagness, 3rd ed., eq. 4.17), so the measured and the
predicted curves must agree. The cylindrical wave leaves through a quiet CPML.

    python vacuum_pulse.py
"""

import numpy as np

import etalon as et

wavelengths = np.linspace(1.30, 1.80, 26)  # µm

sim = et.Simulation(
    size=(8.0, 8.0, 0.0),  # µm; size_z = 0 -> 2D, TE polarisation (Ex, Ey, Hz)
    grid=et.UniformGrid(dl=0.05),  # µm -> 26 to 36 cells per wavelength over the band
    boundary=et.PML(layers=16),  # CPML outside `size`, 0.8 µm: thicker than λ/2
    sources=[
        et.PointSource(
            center=(-3.0, 0.0, 0.0),
            component="Hz",  # magnetic dipole: radiates evenly in every in-plane direction
            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.50),  # µm
            name="dipole",
        )
    ],
    monitors=[
        et.DFTMonitor(
            name="near", center=(-1.0, 0.0, 0.0), wavelengths=wavelengths, components=["Hz"]
        ),
        et.DFTMonitor(
            name="far", center=(3.0, 0.0, 0.0), wavelengths=wavelengths, components=["Hz"]
        ),
        et.DFTMonitor(name="field", size=(7.6, 7.6, 0.0), wavelengths=[1.55]),
    ],
    run_time=300e-15,  # s
)
print(sim.summary())  # cells, time step, number of steps, memory: before spending any time

result = sim.run()

# Phase velocity measured between the probes, normalised to c. The helper removes
# the phase of the 2D cylindrical wave (Hankel H0), leaving the grid's own k.
v_measured = et.analysis.measured_phase_velocity(
    near=result["near"]["Hz"],
    far=result["far"]["Hz"],
    r_near=2.0,  # µm from the source
    r_far=6.0,
    wave="cylindrical",
)
# Yee numerical dispersion for the same cell size, time step and direction (0° = along x)
v_theory = et.analysis.numerical_phase_velocity(wavelengths, grid=result.grid, angle=0.0)

print("wl (um)   v/c measured   v/c Yee theory   difference")
for wl, vm, vt in zip(wavelengths, v_measured, v_theory, strict=True):
    print(f"{wl:7.3f}   {vm:12.6f}   {vt:14.6f}   {vm - vt:+.1e}")
print(f"max |measured - theory| = {np.max(np.abs(v_measured - v_theory)):.1e}  (accept < 5e-3)")
