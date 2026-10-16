"""``etalon studio``: bind 127.0.0.1, print the link, open the browser, serve until Ctrl+C."""

import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path

import uvicorn

from etalon import __version__
from etalon.studio.security import load_or_create_token
from etalon.studio.server import STATIC_DIR, StudioState, create_app
from etalon.studio.settings import SettingsStore, config_dir
from etalon.studio.system import GpuProbe

HOST = "127.0.0.1"
"""Studio never listens on another interface (ui-ux-spec §9)."""


def bind_socket(port: int) -> socket.socket:
    """A socket bound to 127.0.0.1:port; OSError if another program holds the port.

    uvicorn would set SO_REUSEADDR, which on Windows lets a second server take a
    port that is already listening. Binding here makes "port in use" an error on
    every OS: SO_EXCLUSIVEADDRUSE on Windows, plain SO_REUSEADDR (restart without
    waiting for TIME_WAIT) on POSIX.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, port))
    except OSError:
        sock.close()
        raise
    return sock


def say(text: str, error: bool = False) -> None:
    """Print without failing on consoles that cannot encode a path (cp1252, GBK pipes)."""
    stream = sys.stderr if error else sys.stdout
    encoding = stream.encoding or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding) + "\n")
    stream.flush()


def _when_started(server: uvicorn.Server, action: Callable[[], object]) -> None:
    deadline = time.monotonic() + 30.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if server.started:
        action()


def _open_when_ready(server: uvicorn.Server, url: str) -> None:
    _when_started(server, lambda: webbrowser.open(url))


def prepare(folder: Path, port: int) -> tuple[uvicorn.Server, socket.socket, str, GpuProbe] | int:
    """Everything up to serving: the server, its socket, the URL and the (unstarted)
    GPU probe, or an exit code."""
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        say(f"etalon studio: folder not found: {folder}", error=True)
        return 2
    try:
        sock = bind_socket(port)
    except OSError:
        say(
            f"etalon studio: port {port} is in use; is Studio already running? "
            "Use --port to pick another.",
            error=True,
        )
        return 2
    directory = config_dir()
    token = load_or_create_token(directory)
    # Started once the server listens (run()): its process imports CuPy, which would
    # compete with Studio's own start-up. /api/system starts it itself if asked first.
    probe = GpuProbe()
    state = StudioState(
        settings=SettingsStore(directory, folder),
        probe=probe,
        token=token,
        port=port,
        config_dir=directory,
    )
    config = uvicorn.Config(
        create_app(state), host=HOST, port=port, log_level="warning", access_log=False
    )
    url = f"http://{HOST}:{port}/?token={token}"
    if not (STATIC_DIR / "index.html").is_file():
        say("note: the Studio web interface is not built; run `pnpm --dir studio build`.")
    say(f"etalon Studio {__version__}\nworkspace  {folder}\nopen       {url}\nCtrl+C to stop")
    return uvicorn.Server(config), sock, url, probe


def run(folder: Path, port: int, open_browser: bool) -> int:
    prepared = prepare(folder, port)
    if isinstance(prepared, int):
        return prepared
    server, sock, url, probe = prepared
    threading.Thread(target=_when_started, args=(server, probe.start), daemon=True).start()
    if open_browser:
        threading.Thread(target=_open_when_ready, args=(server, url), daemon=True).start()
    server.run(sockets=[sock])
    return 0
