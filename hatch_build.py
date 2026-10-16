"""Hatch build hook: a wheel without the Studio SPA would install a Studio that cannot open."""

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class StudioAssetsHook(BuildHookInterface):  # type: ignore[type-arg]
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel" or version == "editable":
            return
        index = Path(self.root) / "etalon" / "studio" / "static" / "index.html"
        if not index.is_file():
            raise RuntimeError(
                "etalon Studio's web interface is not built; run `pnpm --dir studio install` "
                "and `pnpm --dir studio build` before building a wheel"
            )
