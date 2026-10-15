"""SimulationResult: monitor data as xarray, plus the grid and run metadata."""

from typing import Any

import numpy as np
import xarray as xr
from numpy.typing import NDArray

from etalon.constants import C_0
from etalon.core.simulation import Simulation
from etalon.fdtd.dft import ComponentSampling
from etalon.grid.yee import YeeGrid2D


class SimulationResult:
    """What ``Simulation.run()`` returns.

    ``result["probe"]["Hz"]`` is a complex ``xarray.DataArray`` with dimension
    ``wavelength`` (µm) and, for each monitor axis with size > 0, a dimension
    ``x`` or ``y`` holding that component's own Yee node coordinates (µm).
    Interpolated axes appear as scalar coordinates. Time convention exp(−iωt).
    """

    def __init__(
        self,
        simulation: Simulation,
        grid: YeeGrid2D,
        data: dict[str, dict[str, xr.DataArray]],
        metadata: dict[str, Any],
    ) -> None:
        self.simulation = simulation
        self.grid = grid
        self.data = data
        self.metadata = metadata

    @property
    def monitors(self) -> list[str]:
        return list(self.data)

    def __getitem__(self, name: str) -> dict[str, xr.DataArray]:
        try:
            return self.data[name]
        except KeyError:
            raise KeyError(f"no monitor named {name!r}; monitors: {self.monitors}") from None

    def __repr__(self) -> str:
        meta = self.metadata
        return (
            f"SimulationResult(monitors={self.monitors}, backend={meta['backend']!r}, "
            f"steps={meta['n_steps']}, wall_time={meta['wall_time_s']:.3g} s)"
        )


def monitor_dataarray(sampling: ComponentSampling, acc: NDArray[Any], z: float) -> xr.DataArray:
    """Turn a DFT accumulator (n_f, n_nodes) into a labelled DataArray.

    Axes with size 0 are interpolated here, once, in double precision (the DFT is
    linear, so this equals interpolating the field at every step).
    """
    n_f = sampling.wavelengths.size
    data = acc.reshape(n_f, sampling.x.index.size, sampling.y.index.size).astype(np.complex128)
    dims = []
    coords: dict[str, Any] = {}
    if sampling.x.weights is None:
        dims.append("x")
        coords["x"] = ("x", sampling.x.coords)
    else:
        data = np.einsum("fab,a->fb", data, sampling.x.weights)
        coords["x"] = sampling.x.point
    if sampling.y.weights is None:
        dims.append("y")
        coords["y"] = ("y", sampling.y.coords)
    else:
        data = data @ sampling.y.weights
        coords["y"] = sampling.y.point
    coords["z"] = z
    coords["wavelength"] = ("wavelength", sampling.wavelengths)
    coords["frequency"] = ("wavelength", C_0 / sampling.wavelengths)
    data = np.moveaxis(data, 0, -1).astype(acc.dtype)
    return xr.DataArray(
        data,
        dims=[*dims, "wavelength"],
        coords=coords,
        name=sampling.component,
        attrs={
            "monitor": sampling.monitor,
            "units": "A·s/m" if sampling.is_magnetic else "V·s/m",
            "length_units": "um",
            "time_convention": "exp(-i omega t)",
        },
    )
