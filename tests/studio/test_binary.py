"""The §13.1 binary layout: length, header, padding to 4, float32 little-endian data."""

import json
import struct

import numpy as np
import pytest

from etalon.studio.binary import finite_range, pack, unpack
from etalon.studio.contract import FieldHeader, SnapshotHeader


@pytest.mark.parametrize("component", ["Hz", "Exx", "Eyyy", "Hzzzz"])
def test_data_starts_on_a_multiple_of_4(component):
    data = np.arange(6, dtype=np.float64).reshape(2, 3)
    header = SnapshotHeader(
        shape=(2, 3), extent=(0, 1, 0, 2), min=0, max=5, component=component, unit="A/m", step=7
    )
    buffer = pack(header, data)
    (length,) = struct.unpack_from("<I", buffer)
    start = 4 + length + (-(4 + length) % 4)
    assert start % 4 == 0
    assert buffer[4 + length : start] == b"\0" * (start - 4 - length)
    assert json.loads(buffer[4 : 4 + length])["component"] == component
    values = np.frombuffer(buffer, dtype="<f4", offset=start)
    assert values.tolist() == [0, 1, 2, 3, 4, 5]  # C order: y fastest


def test_round_trip_keeps_header_and_shape():
    data = np.random.default_rng(1).normal(size=(5, 4)).astype(np.float32)
    header = FieldHeader(
        shape=(5, 4),
        extent=(-1.0, 1.0, -0.5, 0.5),
        min=float(data.min()),
        max=float(data.max()),
        component="Ey",
        unit="V·s/m",
        quantity="real",
        wavelength_um=1.55,
    )
    parsed, values = unpack(pack(header, data))
    assert parsed["kind"] == "field"
    assert parsed["unit"] == "V·s/m"
    assert values.dtype == np.dtype("<f4")
    np.testing.assert_array_equal(values, data)


def test_finite_range_ignores_nan_and_inf():
    assert finite_range(np.array([np.nan, -2.0, np.inf, 3.0])) == (-2.0, 3.0)
    assert finite_range(np.array([np.nan])) == (0.0, 0.0)
