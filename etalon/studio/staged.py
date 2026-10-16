"""Serve the Workspace before the whole app is built (plan-u1 §14.1; P3: rows in < 2 s).

U1's routes import NumPy and the solver's models, about 0.5 s of start-up.
``etalon studio`` therefore listens with the quick app (``create_app(state,
full=False)``: U0's routes and the SPA) and builds the full app in a thread once
the first Workspace response has gone out, so the build does not slow the
Workspace, or as soon as a request needs it. Such a request waits for the build.
"""

import asyncio
import sys
import threading
import traceback
from collections.abc import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

QUICK_API_PATHS = frozenset({"/api/workspace", "/api/settings", "/api/system"})
"""What the quick app answers under /api; other /api paths and WebSockets need the full app."""


class StagedApp:
    """ASGI app: the quick app until the full app is built, then the full app."""

    def __init__(self, quick: ASGIApp, build_full: Callable[[], ASGIApp]) -> None:
        self._app = quick
        self._build_full = build_full
        self._lock = threading.Lock()
        self._building = False
        self._built = threading.Event()
        self._failed = False

    def build_soon(self) -> None:
        """Start building the full app in a thread; calling it again does nothing."""
        with self._lock:
            if self._building:
                return
            self._building = True
        threading.Thread(target=self._build, name="etalon-full-app", daemon=True).start()

    def wait_built(self, timeout: float | None = None) -> bool:
        """Block until the build has finished (or failed); False on timeout."""
        return self._built.wait(timeout)

    def _build(self) -> None:
        try:
            self._app = self._build_full()
        except Exception:
            # The terminal running `etalon studio` shows why; requests get a 500, not a hang.
            self._failed = True
            traceback.print_exc(file=sys.stderr)
        finally:
            self._built.set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._app(scope, receive, send)
            return
        if not self._built.is_set():
            if needs_full_app(scope):
                self.build_soon()
                await asyncio.to_thread(self._built.wait)
            elif scope["path"] == "/api/workspace":
                await self._app(scope, receive, send)
                self.build_soon()
                return
        if self._failed and needs_full_app(scope):
            await _unavailable(scope, receive, send)
            return
        await self._app(scope, receive, send)


def needs_full_app(scope: Scope) -> bool:
    if scope["type"] == "websocket":
        return True
    path: str = scope["path"]
    return (path == "/api" or path.startswith("/api/")) and path not in QUICK_API_PATHS


async def _unavailable(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1011})
        return
    body = {
        "code": "api_unavailable",
        "message": "Studio could not load this part of its API; see the terminal running it",
    }
    await JSONResponse(body, status_code=500)(scope, receive, send)
