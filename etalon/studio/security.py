"""The guards in front of Studio's API (ui-ux-spec §9, docs/plan-u0.md §4.2).

- Token: random, created on first launch in the config directory and reused. It
  reaches the browser once as ``?token=``; the SPA then sends it as
  ``X-Etalon-Token`` on every ``/api`` request. Other local processes and other
  users on the machine do not have it.
- Host: only ``127.0.0.1:<port>`` and ``localhost:<port>``, which blocks DNS
  rebinding (a web page whose own domain resolves to 127.0.0.1).
- No CORS headers at all, so the browser refuses cross-origin reads.
- A Content-Security-Policy on HTML pages, so the browser itself refuses to load
  anything from another origin.
"""

import json
import os
import secrets
from pathlib import Path

from starlette.types import ASGIApp, Receive, Scope, Send

TOKEN_FILE = "studio-token"
TOKEN_HEADER = "X-Etalon-Token"
TOKEN_ENV = "ETALON_STUDIO_TOKEN"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data: blob:; font-src 'self'; "
    # Radix injects one <style> element for scroll locking.
    "style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)
HTML_SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def load_or_create_token(directory: Path) -> str:
    """The Studio token: ``ETALON_STUDIO_TOKEN`` if set, else the saved one, else a new one."""
    override = os.environ.get(TOKEN_ENV)
    if override:
        return override
    path = directory / TOKEN_FILE
    if path.exists():
        token = path.read_text(encoding="ascii").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    directory.mkdir(parents=True, exist_ok=True)
    # Owner read/write only on POSIX; Windows applies the user profile's ACL instead.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as file:
        file.write(token + "\n")
    return token


def allowed_hosts(port: int) -> frozenset[str]:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if port == 80:
        hosts |= {"127.0.0.1", "localhost"}
    return frozenset(hosts)


class GuardMiddleware:
    """ASGI middleware: Host check on every request, token check on ``/api``."""

    def __init__(self, app: ASGIApp, token: str, port: int) -> None:
        self.app = app
        self.token = token.encode()
        self.hosts = allowed_hosts(port)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin-1").lower()
        if host not in self.hosts:
            await _reject(scope, send, 400, "bad_host", f"Host {host!r} is not allowed")
            return
        path: str = scope["path"]
        if path == "/api" or path.startswith("/api/"):
            given = headers.get(TOKEN_HEADER.lower().encode(), b"")
            if not secrets.compare_digest(given, self.token):
                await _reject(scope, send, 401, "unauthorized", "missing or wrong Studio token")
                return
        await self.app(scope, receive, send)


async def _reject(scope: Scope, send: Send, status: int, code: str, message: str) -> None:
    if scope["type"] == "websocket":
        # Closing before accepting makes the server answer the handshake with 403.
        await send({"type": "websocket.close", "code": 1008, "reason": code})
        return
    body = json.dumps({"code": code, "message": message}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
