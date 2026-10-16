"""B5: the report, on mocked Meep and etalon result files (no Meep, no GPU)."""

import json

import pytest

from bench.config import load_config
from bench.report import build_rows, render_markdown, write_report
from tests.bench.fakes import default_spectra, device_result, run_record, write


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def meep(cfg, device, s=None, config_sha256=None, **kwargs):
    run = run_record("meep-mpi", s if s is not None else default_spectra(cfg, device), **kwargs)
    extra = {"config_sha256": config_sha256} if config_sha256 else {}
    return device_result(cfg, "2d", device, "meep", [run], **extra)


def etalon(cfg, device, s=None, numpy_s=None, **kwargs):
    s = s if s is not None else default_spectra(cfg, device)
    runs = [run_record("cuda", s, **kwargs), run_record("numpy", numpy_s if numpy_s else s)]
    return device_result(cfg, "2d", device, "etalon", runs)


def unsupported(cfg, device):
    message = "needs M1: ModeSource, ModePortMonitor, PolySlab (not in etalon 0.0.1 yet)"
    runs = [
        run_record(b, None, status="unsupported", needs="M1", message=message)
        for b in ("cuda", "numpy")
    ]
    return device_result(cfg, "2d", device, "etalon", runs)


@pytest.fixture
def root(tmp_path, cfg):
    """A bench tree with every 2D device in a different state."""
    # point2d: both sides, etalon within 1e-6 → compared, passes
    write(tmp_path, meep(cfg, "point2d"))
    t = default_spectra(cfg, "point2d")["T21"]
    write(tmp_path, etalon(cfg, "point2d", {"T21": t + 1e-6}, numpy_s={"T21": t + 2e-6}))
    # straight: etalon cannot run it yet
    write(tmp_path, meep(cfg, "straight"))
    write(tmp_path, unsupported(cfg, "straight"))
    # bend: |S21| off by 0.02 → fails
    s = default_spectra(cfg, "bend")
    write(tmp_path, meep(cfg, "bend", s))
    write(tmp_path, etalon(cfg, "bend", {**s, "S21": s["S21"] * 0.98}))
    # dc: no etalon result
    write(tmp_path, meep(cfg, "dc"))
    # mmi: Meep result from a different config
    write(tmp_path, meep(cfg, "mmi", config_sha256="f" * 64))
    write(tmp_path, etalon(cfg, "mmi"))
    # ring: identical spectra, but etalon's fields have not decayed
    write(tmp_path, meep(cfg, "ring"))
    write(tmp_path, etalon(cfg, "ring", final_decay=1e-3))
    return tmp_path


def test_row_status(cfg, root):
    rows = {row.device: row for row in build_rows(cfg, "2d", root)}
    assert rows["point2d"].status == "compared" and rows["point2d"].passed is True
    assert rows["point2d"].comparison.metrics[0].value == pytest.approx(1e-6, rel=1e-6)
    assert rows["point2d"].cuda_vs_numpy == pytest.approx(1e-6, rel=1e-6)
    assert rows["straight"].status.startswith("needs M1: ModeSource")
    assert rows["straight"].comparison is None
    assert rows["bend"].passed is False
    assert rows["bend"].comparison.metrics[0].value == pytest.approx(0.02 * 0.999, rel=1e-9)
    assert rows["dc"].status == "no etalon result"
    assert rows["mmi"].status == "no Meep result"
    assert any("stale meep result" in note for note in rows["mmi"].notes)
    assert rows["ring"].status == "not converged"
    assert any("1.0e-03" in note for note in rows["ring"].notes)


def test_markdown(cfg, root):
    text = render_markdown(cfg, {"2d": build_rows(cfg, "2d", root)}, "abc1234")
    assert text.startswith("# etalon vs Meep — abc1234")
    table = [line for line in text.splitlines() if line.startswith("| ")]
    by_device = {line.split("|")[1].strip(): line for line in table}
    assert "✓" in by_device["point2d"] and "✗" in by_device["bend"]
    assert "needs M1: ModeSource, ModePortMonitor, PolySlab" in by_device["straight"]
    assert "not converged" in by_device["ring"]
    assert "Meep reference at λ" in text  # straight: Meep-only summary
    assert "2D effective-index model: core n = 2.84778" in text
    assert "10.0 s" in by_device["point2d"]  # wall times


def test_mismatched_wavelengths_are_not_compared(cfg, tmp_path):
    write(tmp_path, meep(cfg, "point2d"))
    other = etalon(cfg, "point2d")
    shifted = other.model_copy(update={"wavelengths_um": [w + 1e-3 for w in other.wavelengths_um]})
    write(tmp_path, shifted)
    rows = {row.device: row for row in build_rows(cfg, "2d", tmp_path)}
    assert rows["point2d"].status.startswith("mismatch")


def test_meep_sanity_flags(cfg, tmp_path):
    s = default_spectra(cfg, "straight")
    write(
        tmp_path, meep(cfg, "straight", {**s, "S21": 0.9 * s["S21"], "S11": 0.2 * s["S11"] / 1e-3})
    )
    rows = {row.device: row for row in build_rows(cfg, "2d", tmp_path)}
    notes = " ".join(rows["straight"].notes)
    assert "|S21| min 0.8991 < 0.99" in notes and "|S11| reaches 0.200" in notes


def test_extrapolated_cpu_time_is_marked(cfg, tmp_path):
    write(tmp_path, meep(cfg, "point2d"))
    s = default_spectra(cfg, "point2d")
    partial = run_record("numpy", None, extrapolated=True, wall_time_s=7200.0 * 3, message="x")
    write(tmp_path, device_result(cfg, "2d", "point2d", "etalon", [run_record("cuda", s), partial]))
    text = render_markdown(cfg, {"2d": build_rows(cfg, "2d", tmp_path)}, "x")
    assert "est. 6.0 h" in text


def test_write_report_keeps_other_sections(cfg, root, tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "abc1234.json").write_text(json.dumps({"m0": {"keep": True}}), encoding="utf-8")
    md = write_report(cfg, ["2d"], "abc1234", results=results, root=root)
    assert md.name == "abc1234.md" and md.exists()
    record = json.loads((results / "abc1234.json").read_text(encoding="utf-8"))
    assert record["m0"] == {"keep": True}
    devices = record["meep_comparison"]["tiers"]["2d"]
    assert devices["point2d"]["passed"] is True and devices["bend"]["passed"] is False
    assert devices["straight"]["status"].startswith("needs M1")
    assert devices["point2d"]["timing_s"]["meep"]["wall"] == 10.0
