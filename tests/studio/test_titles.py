"""Script titles: the module docstring's first line, read with ast, never executed."""

import os

import pytest

from etalon.studio.templates import TEMPLATE_DIR
from etalon.studio.workspace import scan, script_title, title_from_docstring
from tests.studio.conftest import make_client, make_state, write_script


@pytest.mark.parametrize(
    ("docstring", "title"),
    [
        ("Strip waveguide: a silicon strip in silica, driven by a dipole.", "Strip waveguide"),
        ("Strip waveguide: a strip.\n\nMore text: with colons.", "Strip waveguide"),
        ("A 90 degree Euler bend", "A 90 degree Euler bend"),
        ("\n   Leading blank lines: are skipped\n", "Leading blank lines"),
        (": nothing before the colon", ": nothing before the colon"),
        ("   ", "Ring r10 g200"),
        (None, "Ring r10 g200"),
    ],
)
def test_title_from_docstring(docstring, title):
    assert title_from_docstring(docstring, "ring_r10_g200") == title


def test_a_script_with_a_docstring(workspace):
    script = write_script(
        workspace, "strip.py", '"""Strip waveguide: a strip.\n\nDetails."""\n\nimport etalon\n'
    )
    assert script_title(script) == "Strip waveguide"


def test_a_script_without_a_docstring_is_titled_by_its_stem(workspace):
    script = write_script(workspace, "dc_gap200.py", "# a comment\nimport etalon as et\n")
    assert script_title(script) == "Dc gap200"


def test_the_script_is_parsed_not_executed(workspace, tmp_path):
    marker = tmp_path / "ran"
    text = f'"""Side effects: none."""\nopen({str(marker)!r}, "w").close()\n'
    assert script_title(write_script(workspace, "effects.py", text)) == "Side effects"
    assert not marker.exists()


@pytest.mark.parametrize(
    "content",
    [
        b'"""Unfinished: a syntax error below."""\ndef broken(:\n',
        b'"""Null byte: in the file."""\n\x00\n',
        b'"""Not UTF-8: \xff."""\n',
        b"",
    ],
)
def test_a_file_that_does_not_parse_falls_back_to_its_stem(workspace, content):
    script = workspace / "not_python.py"
    script.write_bytes(content)
    assert script_title(script) == "Not python"


def test_a_missing_file_does_not_crash(workspace):
    assert script_title(workspace / "gone_away.py") == "Gone away"


def test_the_title_follows_edits(workspace):
    script = write_script(workspace, "edit.py", '"""Before: x."""\n')
    assert script_title(script) == "Before"
    script.write_text('"""After the edit: y."""\n', encoding="utf-8")
    stat = script.stat()
    os.utime(script, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert script_title(script) == "After the edit"


def test_every_template_has_a_proper_title():
    titles = {path.stem: script_title(path) for path in TEMPLATE_DIR.glob("*.py")}
    assert titles == {
        "phc_waveguide": "Photonic-crystal waveguide",
        "sharp_bend": "Sharp bend",
        "strip_waveguide": "Strip waveguide",
        "vacuum_pulse": "Vacuum pulse",
    }


def test_workspace_rows_carry_titles(workspace, config_dir):
    write_script(workspace, "a/strip.py", '"""Strip waveguide: s."""\n')
    write_script(workspace, "ring_r10.py", "import etalon\n")
    rows = {row.path: row.title for row in scan(workspace).simulations}
    assert rows == {"a/strip.py": "Strip waveguide", "ring_r10.py": "Ring r10"}

    client = make_client(make_state(workspace, config_dir))
    answer = client.get("/api/workspace").json()["simulations"]
    assert [row["title"] for row in answer] == ["Strip waveguide", "Ring r10"]
