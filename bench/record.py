"""bench/results/<git-sha>.json: one record per commit, one section per script.

Several scripts report on the same commit (validate_m0.py writes "m0", report.py writes
"meep_comparison"). Each merges its own top-level section, so neither overwrites the
other.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

BENCH = Path(__file__).parent
RESULTS = BENCH / "results"
REPO = BENCH.parent

# Paths whose changes do not make a benchmark run "dirty": the run's own outputs.
OUTPUTS = ("bench/results", "bench/meep/out", "bench/etalon/out")


def git_sha(repo: Path = REPO) -> str:
    """Short HEAD sha, with "-dirty" if tracked files changed outside OUTPUTS.

    Untracked files (a slide deck, notes) do not count.
    """

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, cwd=repo
        ).stdout.strip()

    try:
        sha = git("rev-parse", "--short", "HEAD")
        excludes = [f":(exclude){path}" for path in OUTPUTS]
        dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", *excludes)
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "nogit"


def update_record(sha: str, section: str, payload: Any, results: Path = RESULTS) -> Path:
    """Set ``section`` of results/<sha>.json to ``payload``, keeping every other section."""
    results.mkdir(parents=True, exist_ok=True)
    path = results / f"{sha}.json"
    record: dict[str, Any] = {}
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
    record["git_sha"] = sha
    record[section] = payload
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path
