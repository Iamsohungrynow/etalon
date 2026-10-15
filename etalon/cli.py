"""The ``etalon`` command.

etalon studio [FOLDER] [--port 8787] [--no-browser]
etalon --version
"""

import argparse
import sys
from pathlib import Path

from etalon import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="etalon", description="etalon: photonic FDTD on one local GPU."
    )
    parser.add_argument("--version", action="version", version=f"etalon {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    studio = commands.add_parser(
        "studio",
        help="open etalon Studio, the local web UI",
        description="Open etalon Studio on http://127.0.0.1:PORT. Nothing leaves this machine.",
    )
    studio.add_argument(
        "folder",
        nargs="?",
        default=".",
        type=Path,
        help="workspace folder whose .py simulation scripts Studio lists (default: here)",
    )
    studio.add_argument("--port", type=int, default=8787, help="port on 127.0.0.1 (default 8787)")
    studio.add_argument(
        "--no-browser", action="store_true", help="print the link instead of opening a browser"
    )
    args = parser.parse_args(argv)
    if args.command == "studio":
        # Imported here so `etalon --version` does not load FastAPI.
        from etalon.studio.launch import run

        return run(args.folder, port=args.port, open_browser=not args.no_browser)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
