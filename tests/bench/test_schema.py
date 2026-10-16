"""B3: the result-file schema both sides write."""

import json

import numpy as np
import pytest
from pydantic import ValidationError

from bench.config import load_config
from bench.schema import code_sha256, decode_complex, encode_complex, read_result, write_result
from tests.bench.fakes import default_spectra, device_result, run_record


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_complex_round_trip():
    values = np.array([1 + 2j, -0.5j, 3.0])
    encoded = encode_complex(values)
    assert encoded == [(1.0, 2.0), (0.0, -0.5), (3.0, 0.0)]
    assert np.array_equal(decode_complex(encoded), values)


def test_write_and_read_back(tmp_path, cfg):
    result = device_result(
        cfg, "2d", "dc", "meep", [run_record("meep-mpi", default_spectra(cfg, "dc"))]
    )
    path = tmp_path / "dc.json"
    write_result(path, result)
    assert read_result(path) == result
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["schema"] == "etalon-bench/1"
    assert abs(complex(*data["runs"][0]["s"]["S31"][0])) == pytest.approx(np.sqrt(0.55))
    # every [re, im] pair and every flat list sits on one line
    assert '"wavelengths_um": [1.5, ' in text
    assert "\n   -" not in text and text.count("\n") < 600


def test_rejects_inconsistent_files(cfg):
    good = default_spectra(cfg, "dc")
    with pytest.raises(ValidationError, match="S key"):
        device_result(cfg, "2d", "dc", "meep", [run_record("meep-mpi", {"S91": good["S31"]})])
    with pytest.raises(ValidationError, match="wavelengths"):
        device_result(cfg, "2d", "dc", "meep", [run_record("meep-mpi", {"S31": good["S31"][:5]})])
    with pytest.raises(ValidationError):
        bad = {"S31": np.full(good["S31"].shape, np.nan + 0j)}
        device_result(cfg, "2d", "dc", "meep", [run_record("meep-mpi", bad)])
    with pytest.raises(ValidationError, match="S-parameters"):
        run_record("cuda", None)
    with pytest.raises(ValidationError, match="must say why"):
        run_record("cuda", None, status="unsupported")
    with pytest.raises(ValidationError):
        run_record("gpu", good)


def test_code_hash_ignores_line_endings(tmp_path):
    (tmp_path / "a.py").write_bytes(b"x = 1\ny = 2\n")
    first = code_sha256(("a.py",), tmp_path)
    (tmp_path / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    assert code_sha256(("a.py",), tmp_path) == first
    (tmp_path / "a.py").write_bytes(b"x = 1\ny = 3\n")
    assert code_sha256(("a.py",), tmp_path) != first
