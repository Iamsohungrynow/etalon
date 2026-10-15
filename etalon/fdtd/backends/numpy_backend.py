"""NumPy reference backend for 2D TE.

This is the definition of what the CUDA kernels in ``cuda/update_te.cu`` and
``cuda/dft.cu`` compute: same equations, same operands, same order of
floating-point operations (the kernels are compiled with --fmad=false), so the
two backends agree to rounding and usually bit for bit.

Yee update with CPML (Taflove & Hagness, 3rd ed., ch. 3 and 7; Roden & Gedney 2000):

    Hz += Δt/μ0 · [ (∂y Ex / κy + ψ_Hz,y) − (∂x Ey / κx + ψ_Hz,x) ]
    Ex += Δt/ε  ·   (∂y Hz / κy + ψ_Ex,y)                 (j = 1 … ny−1)
    Ey −= Δt/ε  ·   (∂x Hz / κx + ψ_Ey,x)                 (i = 1 … nx−1)

with ψ ← b ψ + c ∂F and centred differences. Tangential E on the outer
boundary (Ex at j = 0, ny; Ey at i = 0, nx) is never updated: PEC behind the PML.
"""

from typing import Any

import numpy as np

from etalon.fdtd.state import TEState


class NumpyBackend:
    """Reference implementation; runs everywhere."""

    name = "numpy"
    device = "cpu"
    xp = np

    def to_device(self, a: np.ndarray) -> np.ndarray:
        return a

    def to_host(self, a: Any) -> np.ndarray:
        return np.asarray(a)

    def synchronize(self) -> None:
        pass

    def update_h_te(self, s: TEState) -> None:
        """Hz^(n−½) → Hz^(n+½) from Ex^n, Ey^n."""
        dex_dy = (s.ex[:, 1:] - s.ex[:, :-1]) * s.inv_dy  # at Hz nodes, (nx, ny)
        dey_dx = (s.ey[1:, :] - s.ey[:-1, :]) * s.inv_dx  # at Hz nodes, (nx, ny)
        s.psi_hz_y[...] = s.by_h[None, :] * s.psi_hz_y + s.cy_h[None, :] * dex_dy
        s.psi_hz_x[...] = s.bx_h[:, None] * s.psi_hz_x + s.cx_h[:, None] * dey_dx
        s.hz += s.db * (
            (dex_dy * s.iky_h[None, :] + s.psi_hz_y) - (dey_dx * s.ikx_h[:, None] + s.psi_hz_x)
        )

    def update_e_te(self, s: TEState) -> None:
        """Ex^n, Ey^n → Ex^(n+1), Ey^(n+1) from Hz^(n+½)."""
        dhz_dy = (s.hz[:, 1:] - s.hz[:, :-1]) * s.inv_dy  # at Ex nodes j = 1 … ny−1
        psi = s.psi_ex_y[:, 1:-1]
        psi[...] = s.by_e[None, 1:-1] * psi + s.cy_e[None, 1:-1] * dhz_dy
        s.ex[:, 1:-1] += s.cb_ex[:, 1:-1] * (dhz_dy * s.iky_e[None, 1:-1] + psi)

        dhz_dx = (s.hz[1:, :] - s.hz[:-1, :]) * s.inv_dx  # at Ey nodes i = 1 … nx−1
        psi = s.psi_ey_x[1:-1, :]
        psi[...] = s.bx_e[1:-1, None] * psi + s.cx_e[1:-1, None] * dhz_dx
        s.ey[1:-1, :] -= s.cb_ey[1:-1, :] * (dhz_dx * s.ikx_e[1:-1, None] + psi)

    def accumulate_dft(
        self, acc: np.ndarray, field: np.ndarray, index: np.ndarray, phasors: np.ndarray
    ) -> None:
        """acc[f, k] += field.flat[index[k]] · phasors[f]."""
        acc += field.ravel()[index][None, :] * phasors[:, None]
