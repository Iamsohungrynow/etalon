"""etalon benchmark harness: etalon vs Meep on the reference devices (docs/plan-bench.md).

The shared modules here (config, devices, schema) are imported by BOTH sides: by the etalon
side in etalon's environment, and by bench/meep/run_device.py in the separate Meep
environment. So they depend on numpy, pydantic and pyyaml only, and never import etalon or
meep. Only bench/meep/ imports meep; nothing in bench/meep/ imports etalon.
"""
