"""Binary float32 arrays with a JSON header (plan-u1 §13.1).

    [uint32 little-endian N][N bytes UTF-8 JSON header][zero padding][float32 little-endian data]

The data starts at ``4 + N`` rounded up to a multiple of 4, so the browser can
view it as a ``Float32Array`` without copying. The same layout serves the
permittivity slice, monitor fields and live snapshots.
"""

import json
import struct
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel

MEDIA_TYPE = "application/octet-stream"


def pack(header: BaseModel, data: NDArray[Any]) -> bytes:
    """Header and data in the §13.1 layout; ``data`` is cast to float32 in C order."""
    text = json.dumps(header.model_dump(mode="json"), separators=(",", ":"), allow_nan=False)
    head = text.encode("utf-8")
    start = 4 + len(head)
    padding = b"\0" * (-start % 4)
    values = np.ascontiguousarray(data, dtype="<f4")
    return struct.pack("<I", len(head)) + head + padding + values.tobytes()


def unpack(buffer: bytes) -> tuple[dict[str, Any], NDArray[np.float32]]:
    """The header and the data reshaped to ``header["shape"]`` (used by tests and tools)."""
    (length,) = struct.unpack_from("<I", buffer, 0)
    header: dict[str, Any] = json.loads(buffer[4 : 4 + length].decode("utf-8"))
    start = 4 + length + (-(4 + length) % 4)
    data = np.frombuffer(buffer, dtype="<f4", offset=start)
    return header, data.reshape(header["shape"])


def finite_range(data: NDArray[Any]) -> tuple[float, float]:
    """(min, max) of the finite values, or (0, 0) when there are none."""
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return 0.0, 0.0
    return float(finite.min()), float(finite.max())


def node_extent(x: NDArray[Any], y: NDArray[Any]) -> tuple[float, float, float, float]:
    """[x_first, x_last, y_first, y_last] of node coordinate rows, µm."""
    return float(x[0]), float(x[-1]), float(y[0]), float(y[-1])
