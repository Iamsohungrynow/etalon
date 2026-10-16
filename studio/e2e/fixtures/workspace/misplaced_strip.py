"""Misplaced strip: a Studio e2e fixture, the strip template with its strip in the wrong place.

The strip was meant to run along y = 0, through the dipole; a sign slip moved it
to y = 0.6 µm. The script runs, but the dipole sits in SiO2 and nothing is
guided. The Setup slice shows it: εr at (0, 0) is SiO2's 2.085, and the
silicon stripe (εr 12.08) covers y = 0.35 … 0.85 µm.
"""

import numpy as np

import etalon as et

si = et.Medium(n=3.476, name="Si")
sio2 = et.Medium(n=1.444, name="SiO2")
wavelengths = [1.50, 1.55, 1.60]  # µm

sim = et.Simulation(
    size=(4.0, 2.0, 0.0),  # µm, 2D TE (Ex, Ey, Hz)
    medium=sio2,
    structures=[
        # Longer than the region, so the strip continues into the PML.
        et.Box(center=(0.0, 0.6, 0.0), size=(8.0, 0.5, 0.0), medium=si, name="strip"),
    ],
    grid=et.UniformGrid(dl=0.02),  # 20 cells per wavelength in Si at 1.40 µm
    boundary=et.PML(layers=28),  # 0.56 µm: more than half a wavelength in SiO2
    sources=[
        et.PointSource(
            center=(-1.5, 0.05, 0.0),  # off-centre, so odd modes are excited as well
            component="Hz",
            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.3),
            name="dipole",
        )
    ],
    monitors=[
        et.DFTMonitor(name="field", size=(3.8, 1.8, 0.0), wavelengths=wavelengths),
        et.DFTMonitor(
            name="end", center=(1.5, 0.0, 0.0), wavelengths=wavelengths, components=["Hz"]
        ),
    ],
    run_time=120e-15,  # s
)
print(sim.summary())

result = sim.run()

hz = result["end"]["Hz"]
for wl, value in zip(wavelengths, hz.values, strict=True):
    print(f"|Hz| at the far end, {wl:.2f} um: {np.abs(value):.3e} A*s/m")
