"""CUDA backend: the NumPy reference as CuPy RawKernels.

The kernels are CUDA C in ``cuda/update_te.cu`` and ``cuda/dft.cu``, compiled once
per precision with ``REAL`` = float or double and ``--fmad=false``, so every
multiply and add rounds separately, as in NumPy. Array layout, operand order and
the equations are those of ``numpy_backend.py``; tests/gpu checks the two agree.
"""

from pathlib import Path
from typing import Any

import cupy as cp
import numpy as np

from etalon.fdtd.state import TEState

_CUDA_DIR = Path(__file__).parent / "cuda"
_BLOCK_2D = (32, 8, 1)  # x along y (contiguous), y along x
_BLOCK_DFT = 128


def _blocks(n_fast: int, n_slow: int) -> tuple[int, int, int]:
    return (
        (n_fast + _BLOCK_2D[0] - 1) // _BLOCK_2D[0],
        (n_slow + _BLOCK_2D[1] - 1) // _BLOCK_2D[1],
        1,
    )


class CupyBackend:
    """One NVIDIA GPU (the current CuPy device)."""

    name = "cuda"
    xp = cp

    def __init__(self, precision: str) -> None:
        try:
            n_devices = cp.cuda.runtime.getDeviceCount()
        except cp.cuda.runtime.CUDARuntimeError as error:
            raise RuntimeError(f"backend='cuda' found no usable NVIDIA driver ({error})") from error
        if n_devices == 0:
            raise RuntimeError("backend='cuda' found no CUDA device")
        real = {"single": "float", "double": "double"}[precision]
        sources = [(_CUDA_DIR / name).read_text() for name in ("update_te.cu", "dft.cu")]
        code = "\n".join([f"#define REAL {real}", *sources])
        try:
            module = cp.RawModule(code=code, options=("--fmad=false",))
            self._update_h = module.get_function("update_h_te")
            self._update_e = module.get_function("update_e_te")
            self._dft = module.get_function("accumulate_dft")
        except Exception as error:
            raise RuntimeError(
                "backend='cuda' could not compile its kernels; CuPy needs the CUDA headers and "
                "NVRTC (a CUDA toolkit, or `pip install cupy-cuda12x[ctk]`). "
                f"Original error: {error}"
            ) from error
        device_id = cp.cuda.Device().id
        name = cp.cuda.runtime.getDeviceProperties(device_id)["name"].decode()
        self.device = f"cuda:{device_id} {name}"

    def to_device(self, a: np.ndarray) -> Any:
        return cp.asarray(a)

    def to_host(self, a: Any) -> np.ndarray:
        return np.asarray(cp.asnumpy(a))

    def synchronize(self) -> None:
        cp.cuda.Device().synchronize()

    def update_h_te(self, s: TEState) -> None:
        self._update_h(
            _blocks(s.ny, s.nx),
            _BLOCK_2D,
            (
                s.hz, s.ex, s.ey, s.psi_hz_x, s.psi_hz_y,
                s.bx_h, s.cx_h, s.ikx_h, s.by_h, s.cy_h, s.iky_h,
                s.db, s.inv_dx, s.inv_dy, np.int32(s.nx), np.int32(s.ny),
            ),
        )  # fmt: skip

    def update_e_te(self, s: TEState) -> None:
        self._update_e(
            _blocks(s.ny + 1, s.nx + 1),
            _BLOCK_2D,
            (
                s.ex, s.ey, s.hz, s.psi_ex_y, s.psi_ey_x, s.cb_ex, s.cb_ey,
                s.bx_e, s.cx_e, s.ikx_e, s.by_e, s.cy_e, s.iky_e,
                s.inv_dx, s.inv_dy, np.int32(s.nx), np.int32(s.ny),
            ),
        )  # fmt: skip

    def accumulate_dft(self, acc: Any, field: Any, index: Any, phasors: Any) -> None:
        n_f, n_nodes = acc.shape
        self._dft(
            ((n_nodes + _BLOCK_DFT - 1) // _BLOCK_DFT, n_f, 1),
            (_BLOCK_DFT, 1, 1),
            (acc, field, index, phasors, np.int32(n_f), np.int32(n_nodes)),
        )
