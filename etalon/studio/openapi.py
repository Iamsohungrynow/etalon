"""Write Studio's OpenAPI schema for the frontend's generated types.

    python -m etalon.studio.openapi [PATH]   (default: studio/src/api/openapi.json)

Then ``pnpm --dir studio gen:api`` turns it into ``studio/src/api/schema.ts``.
Both files are committed; tests fail when either is stale.
"""

import json
import sys
from pathlib import Path
from typing import Any

from etalon.studio.server import StudioState, create_app
from etalon.studio.settings import SettingsStore
from etalon.studio.system import GpuProbe

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "studio" / "src" / "api" / "openapi.json"


def build_schema() -> dict[str, Any]:
    """The schema of an app that touches no disk and starts no probe."""
    state = StudioState(
        settings=SettingsStore(None, Path.cwd()),
        probe=GpuProbe(command=[sys.executable, "-c", ""]),
        token="schema",
        port=8787,
    )
    return create_app(state).openapi()


def schema_text() -> str:
    return json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(schema_text(), encoding="utf-8", newline="\n")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
