"""B7: the GPL boundary, checked statically (AST) over the whole repository.

* Nothing outside bench/meep/ imports meep (Meep is GPL-2.0-or-later; CLAUDE.md).
* Nothing in bench/meep/ imports etalon, so the Meep reference stays independent.
* The modules the Meep environment loads import only what that environment has.
"""

import ast
import sys
from pathlib import Path

import pytest

from bench.schema import MEEP_CODE_FILES

REPO = Path(__file__).resolve().parents[2]
SKIP = {".venv", ".git", "node_modules", "studio", "__pycache__"}

# What bench/meep/env.yaml provides, besides the standard library.
MEEP_ENV = {"meep", "mpi4py", "numpy", "yaml", "pydantic", "bench"}


def python_files():
    for path in REPO.rglob("*.py"):
        if not SKIP.intersection(path.relative_to(REPO).parts):
            yield path


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def is_meep_side(path: Path) -> bool:
    return path.is_relative_to(REPO / "bench" / "meep")


def test_meep_is_imported_only_in_bench_meep():
    offenders = [
        str(path.relative_to(REPO))
        for path in python_files()
        if not is_meep_side(path)
        and any(m == "meep" or m.startswith("meep.") for m in imported_modules(path))
    ]
    assert offenders == []


def test_meep_side_never_imports_etalon():
    meep_side = [p for p in python_files() if is_meep_side(p)]
    assert meep_side, "bench/meep/ should hold the Meep scripts"
    for path in meep_side:
        for module in imported_modules(path):
            top = module.split(".")[0]
            assert top != "etalon", f"{path} imports {module}"
            assert not module.startswith("bench.etalon"), f"{path} imports {module}"


@pytest.mark.parametrize("name", MEEP_CODE_FILES)
def test_meep_environment_has_every_import(name):
    for module in imported_modules(REPO / "bench" / name):
        top = module.split(".")[0]
        assert top in MEEP_ENV or top in sys.stdlib_module_names, f"bench/{name} imports {module}"
        if top == "bench":
            assert module in {"bench.config", "bench.devices", "bench.schema"}, module


def test_no_module_named_meep_shadows_pymeep():
    """`import meep` must resolve to pymeep: no meep.py and no importable bench-level `meep`."""
    assert not (REPO / "meep").exists() and not (REPO / "meep.py").exists()
    assert not (REPO / "bench" / "meep" / "meep.py").exists()
