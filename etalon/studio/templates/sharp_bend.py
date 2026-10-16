"""Sharp bend: two silicon strips meeting at a right angle, and what the corner radiates.

Light guided along x in a 0.5 µm strip turns into a strip along y at a sharp
90° corner. Part of it follows the bend, part reflects and part radiates into
the SiO2 cladding: the reason real bends are curved. The plane monitor shows
the radiation; the two point monitors compare the input and output arms.

    python sharp_bend.py
"""

import numpy as np

import etalon as et

si = et.Medium(n=3.476, name="Si")
sio2 = et.Medium(n=1.444, name="SiO2")
wavelengths = [1.50, 1.55, 1.60]  # µm
width = 0.5  # µm
corner = 0.5  # µm, x and y of the corner's centre

sim = et.Simulation(
    size=(4.0, 4.0, 0.0),  # µm, 2D TE (Ex, Ey, Hz)
    medium=sio2,
    structures=[
        # Input arm along x, from beyond the left edge to the far side of the corner.
        et.Box(
            center=((corner + width / 2 - 3.0) / 2, corner, 0.0),
            size=(corner + width / 2 + 3.0, width, 0.0),
            medium=si,
            name="input",
        ),
        # Output arm along y, from the corner to beyond the top edge.
        et.Box(
            center=(corner, (corner - width / 2 + 3.0) / 2, 0.0),
            size=(width, 3.0 - corner + width / 2, 0.0),
            medium=si,
            name="output",
        ),
    ],
    grid=et.UniformGrid(dl=0.02),
    boundary=et.PML(layers=28),
    sources=[
        et.PointSource(
            center=(-1.5, corner, 0.0),
            component="Hz",
            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.3),
            name="dipole",
        )
    ],
    monitors=[
        et.DFTMonitor(name="field", size=(3.8, 3.8, 0.0), wavelengths=wavelengths),
        et.DFTMonitor(
            name="in", center=(-0.8, corner, 0.0), wavelengths=wavelengths, components=["Hz"]
        ),
        et.DFTMonitor(
            name="out", center=(corner, 1.6, 0.0), wavelengths=wavelengths, components=["Hz"]
        ),
    ],
    run_time=150e-15,  # s
)
print(sim.summary())

result = sim.run()

ratio = np.abs(result["out"]["Hz"].values) / np.abs(result["in"]["Hz"].values)
for wl, value in zip(wavelengths, ratio, strict=True):
    print(f"|Hz out| / |Hz in| at {wl:.2f} um: {value:.3f}")
