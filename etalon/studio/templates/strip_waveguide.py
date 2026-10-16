"""Strip waveguide: a silicon strip in silica, driven by a dipole inside it.

A 0.5 µm wide strip of n = 3.476 runs along x through SiO2 (n = 1.444) and out
through the PML at both ends. A magnetic dipole (Hz) near the left end excites
the strip's guided modes; whatever is not guided radiates into the cladding.
The plane monitor shows the field at three wavelengths and the point monitor
the spectrum carried to the far end.

    python strip_waveguide.py
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
        et.Box(center=(0.0, 0.0, 0.0), size=(8.0, 0.5, 0.0), medium=si, name="strip"),
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
