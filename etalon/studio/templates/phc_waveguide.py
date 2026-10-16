"""Photonic-crystal waveguide: a line defect in a square lattice of air holes in silicon.

Square air holes on a square lattice (period a = 0.42 µm) perforate silicon;
for the 2D TE polarisation simulated here (Ex, Ey, Hz) such a connected
dielectric has a band gap around 1.55 µm. One row of holes is left out, and the
light launched into that solid line stays in it: the lattice on either side
forbids it to spread. (A lattice of isolated rods would not do this in TE: its
gap is for the other polarisation, Ez.)

    python phc_waveguide.py
"""

import numpy as np

import etalon as et

si = et.Medium(n=3.476, name="Si")
air = et.Medium(n=1.0, name="air")
a = 0.42  # µm, lattice period
hole = 0.34  # µm, side of a square hole
periods, rows = 12, 3  # holes along x; rows on each side of the line
wavelengths = [1.50, 1.55, 1.60]  # µm

holes = [
    et.Box(
        center=((i - (periods - 1) / 2) * a, j * a, 0.0),
        size=(hole, hole, 0.0),
        medium=air,
        name=f"hole {i},{j}",
    )
    for j in range(-rows, rows + 1)
    if j != 0  # the missing row: the waveguide
    for i in range(periods)
]

sim = et.Simulation(
    size=(periods * a, (2 * rows + 1) * a, 0.0),  # µm, 2D TE (Ex, Ey, Hz)
    medium=si,  # the holes are cut out of silicon; the PML is plain silicon
    structures=holes,
    grid=et.UniformGrid(dl=0.02),  # 21 cells per wavelength in Si at 1.45 µm
    boundary=et.PML(layers=12),  # 0.24 µm: more than half a wavelength in Si
    sources=[
        et.PointSource(
            center=(-(periods * a) / 2 + 0.4, 0.0, 0.0),
            component="Hz",
            pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.2),
            name="dipole",
        )
    ],
    monitors=[
        et.DFTMonitor(
            name="field",
            size=(periods * a - 0.12, (2 * rows + 1) * a - 0.12, 0.0),
            wavelengths=wavelengths,
        ),
        et.DFTMonitor(
            name="in", center=(-1.4, 0.0, 0.0), wavelengths=wavelengths, components=["Hz"]
        ),
        et.DFTMonitor(
            name="out", center=(2.0, 0.0, 0.0), wavelengths=wavelengths, components=["Hz"]
        ),
    ],
    run_time=250e-15,  # s
)
print(sim.summary())

result = sim.run()

ratio = np.abs(result["out"]["Hz"].values) / np.abs(result["in"]["Hz"].values)
for wl, value in zip(wavelengths, ratio, strict=True):
    print(f"|Hz out| / |Hz in| at {wl:.2f} um: {value:.3f}")
