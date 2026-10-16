"""Broken script: a Studio e2e fixture that fails at line 12, for the traceback view."""

import etalon as et

si = et.Medium(n=3.476, name="Si")
sio2 = et.Medium(n=1.444, name="SiO2")
gaps = {"ring": 0.2, "bus": 0.3}  # µm

print("building the coupler")
width = 0.5
# The typo on the next line is the point of this fixture: KeyError 'rnig'.
gap = gaps["rnig"]
