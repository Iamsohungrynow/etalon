"""Backend selection: NumPy (reference, CPU) or CUDA (CuPy RawKernels).

Both expose the same methods: to_device, to_host, synchronize, update_h_te,
update_e_te, accumulate_dft, plus ``xp`` (the array module), ``name`` and ``device``.
"""

import logging
import warnings
from typing import Any

from etalon.fdtd.backends.numpy_backend import NumpyBackend

log = logging.getLogger("etalon")


def get_backend(name: str, precision: str) -> Any:
    """The backend for ``Simulation.backend``.

    "cuda" raises if CuPy or a GPU is missing — never a silent fallback. "auto" uses
    CUDA when CuPy and a device are present, NumPy otherwise; if a device is present
    but CUDA fails to initialise, it warns and uses NumPy.
    """
    if name == "numpy":
        return NumpyBackend()
    if name == "cuda":
        return _cuda_backend(precision)
    if name == "auto":
        try:
            import cupy

            n_devices = cupy.cuda.runtime.getDeviceCount()
        except Exception:  # CuPy missing, or no driver: plain CPU machine
            log.info("etalon: no CUDA device found, using the NumPy backend")
            return NumpyBackend()
        if n_devices == 0:
            log.info("etalon: no CUDA device found, using the NumPy backend")
            return NumpyBackend()
        try:
            return _cuda_backend(precision)
        except RuntimeError as error:
            warnings.warn(f"{error}\nFalling back to the NumPy backend.", stacklevel=3)
            return NumpyBackend()
    raise ValueError(f"unknown backend {name!r}; use 'auto', 'numpy' or 'cuda'")


def _cuda_backend(precision: str) -> Any:
    try:
        from etalon.fdtd.backends.cupy_backend import CupyBackend
    except ImportError as error:
        raise RuntimeError(
            f"backend='cuda' needs CuPy: install etalon[gpu], or use backend='numpy' ({error})"
        ) from error
    return CupyBackend(precision)
