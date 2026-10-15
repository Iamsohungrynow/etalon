"""Arrays a 2D TE time step reads and writes, on whichever device the backend uses."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from etalon.constants import EPSILON_0, MU_0, UM
from etalon.fdtd.cpml import CPMLAxis
from etalon.grid.yee import YeeGrid2D


@dataclass
class TEState:
    """Fields, CPML auxiliaries and coefficients for 2D TE (shapes in etalon.grid.yee).

    Coefficient naming: ``b``, ``c``, ``ik`` (1/κ) for the CPML; suffix ``x``/``y`` is
    the axis, ``e``/``h`` the node type (integer / half). ``cb_ex`` = Δt/(ε0 ε_r) at
    the Ex nodes, ``db`` = Δt/μ0, ``inv_dx`` = 1/Δx in 1/m.
    """

    ex: Any
    ey: Any
    hz: Any
    psi_ex_y: Any
    psi_ey_x: Any
    psi_hz_x: Any
    psi_hz_y: Any
    cb_ex: Any
    cb_ey: Any
    bx_e: Any
    cx_e: Any
    ikx_e: Any
    bx_h: Any
    cx_h: Any
    ikx_h: Any
    by_e: Any
    cy_e: Any
    iky_e: Any
    by_h: Any
    cy_h: Any
    iky_h: Any
    db: Any
    inv_dx: Any
    inv_dy: Any
    nx: int
    ny: int


def build_te_state(
    grid: YeeGrid2D,
    eps_r: dict[str, NDArray[np.float64]],
    cpml_x: CPMLAxis,
    cpml_y: CPMLAxis,
    dtype: type[np.floating[Any]],
    to_device: Callable[[NDArray[Any]], Any],
) -> TEState:
    """Zero fields; coefficients computed in float64 on the host, then cast once to ``dtype``.

    Casting identical float64 arrays is what lets both backends start from bit-identical
    inputs.
    """

    def put(a: NDArray[np.float64]) -> Any:
        return to_device(np.ascontiguousarray(a, dtype=dtype))

    def zeros(component: str) -> Any:
        return put(np.zeros(grid.shape(component)))

    return TEState(
        ex=zeros("Ex"),
        ey=zeros("Ey"),
        hz=zeros("Hz"),
        psi_ex_y=zeros("Ex"),
        psi_ey_x=zeros("Ey"),
        psi_hz_x=zeros("Hz"),
        psi_hz_y=zeros("Hz"),
        cb_ex=put(grid.dt / (EPSILON_0 * eps_r["Ex"])),
        cb_ey=put(grid.dt / (EPSILON_0 * eps_r["Ey"])),
        bx_e=put(cpml_x.b_e),
        cx_e=put(cpml_x.c_e),
        ikx_e=put(cpml_x.inv_kappa_e),
        bx_h=put(cpml_x.b_h),
        cx_h=put(cpml_x.c_h),
        ikx_h=put(cpml_x.inv_kappa_h),
        by_e=put(cpml_y.b_e),
        cy_e=put(cpml_y.c_e),
        iky_e=put(cpml_y.inv_kappa_e),
        by_h=put(cpml_y.b_h),
        cy_h=put(cpml_y.c_h),
        iky_h=put(cpml_y.inv_kappa_h),
        db=dtype(grid.dt / MU_0),
        inv_dx=dtype(1.0 / (grid.dx * UM)),
        inv_dy=dtype(1.0 / (grid.dy * UM)),
        nx=grid.nx,
        ny=grid.ny,
    )
