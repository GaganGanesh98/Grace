"""Transports for the MCP governance server: stdio and streamable HTTP.

Two trust boundaries, deliberately handled differently:

**stdio** — the server is a subprocess of the agent runtime on the same
machine. There is no network hop and no per-request identity, so the key is
read once from ``AXIOM_API_KEY`` and bound for the process lifetime. Anything
able to read that environment variable could already impersonate the process.

**HTTP** — the key arrives per request in the ``Authorization`` header, is
resolved against the database, and is bound only for the duration of that
request via a context variable. Nothing is cached across requests beyond what
``verify_key`` itself does.

Write tools re-verify the key on every call in both transports (see
``auth.reverify_for_write``), so a revoked key stops working immediately
rather than at the end of a long-lived session.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from typing import Any

import structlog

from axiom.db import session_scope
from axiom.mcp.auth import (
    API_KEY_ENV_VAR,
    MCPAuthError,
    api_key_from_env,
    extract_bearer,
    reset_principal,
    resolve_principal,
    set_principal,
)
from axiom.mcp.server import MCPServer, build_server

logger = structlog.get_logger(__name__)

_server: MCPServer | None = None


def get_server() -> MCPServer:
    """Return the process-wide MCP server, building it on first use.

    A single instance is shared between ``build_http_app`` and
    ``session_manager_lifespan`` — they must reference the *same* server or the
    lifespan would start a session manager belonging to a different object than
    the one serving requests.
    """

    global _server
    if _server is None:
        _server = build_server()
    return _server


Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]


async def _send_401(send: Send, message: str) -> None:
    body = b'{"error":"unauthorized","detail":"' + message.replace('"', "'").encode("utf-8") + b'"}'
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b'Bearer realm="grace-mcp"'),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class MCPAuthMiddleware:
    """ASGI middleware resolving an API key into a principal per request.

    Sits in front of the MCP ASGI app so that no MCP message is ever
    dispatched without an authenticated principal bound to the context.
    """

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            # Grace's MCP surface is HTTP-only; websocket/lifespan pass through.
            await self._app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        presented = extract_bearer(headers)

        try:
            async with session_scope() as db:
                principal = await resolve_principal(db, presented)
        except MCPAuthError as exc:
            logger.info("mcp.http.auth_failed", path=scope.get("path"))
            await _send_401(send, str(exc))
            return

        token = set_principal(principal)
        try:
            await self._app(scope, receive, send)
        finally:
            reset_principal(token)


def build_http_app() -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    """Return the authenticated MCP ASGI app for mounting at ``/mcp``.

    ``streamable_http_path="/"`` because the app is mounted *under* ``/mcp``;
    leaving the SDK default would serve the endpoint at ``/mcp/mcp``.

    The canonical endpoint is therefore ``/mcp/`` **with** the trailing slash,
    and clients must be configured with it. FastAPI's router answers ``/mcp``
    with a 307 to ``/mcp/``; that redirect carries no body and no content-type,
    and the official MCP SDK client does not follow it — it aborts the
    handshake with ``Unexpected content type:``. Verified against
    mcp==2.0.0: the bare path fails, the slashed path completes the
    initialize/list_tools/call_tool round trip. ``docs/MCP.md`` advertises the
    slashed form for this reason, not merely to save a round trip.

    IMPORTANT: the Starlette app returned by ``streamable_http_app()`` carries
    its own lifespan (``session_manager.run()``), and **FastAPI does not run
    the lifespan of a mounted sub-application**. Callers must therefore also
    enter ``session_manager_lifespan()`` from the parent app's lifespan, or the
    session manager never starts and every request fails at runtime.
    """

    mcp = get_server()
    return MCPAuthMiddleware(mcp.streamable_http_app(streamable_http_path="/"))


@asynccontextmanager
async def session_manager_lifespan() -> AsyncIterator[None]:
    """Run the MCP session manager for the lifetime of the parent app."""

    mcp = get_server()
    async with mcp.session_manager.run():
        logger.info("mcp.session_manager.started")
        yield
    logger.info("mcp.session_manager.stopped")


async def _serve_stdio() -> int:
    """Resolve the environment key, then serve MCP over stdio."""

    presented = api_key_from_env()
    if not presented:
        # stdout is the MCP wire on this transport — diagnostics must go to
        # stderr, and must not use print() (blocked in backend source).
        sys.stderr.write(
            f"error: {API_KEY_ENV_VAR} is not set. Mint a key with the "
            "'mcp:read' and 'mcp:write' scopes and export it before starting "
            "the Grace MCP server.\n"
        )
        return 2

    try:
        async with session_scope() as db:
            principal = await resolve_principal(db, presented)
    except MCPAuthError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 3

    set_principal(principal)
    logger.info(
        "mcp.stdio.authenticated",
        project_id=str(principal.ctx.project_id),
        scopes=list(principal.scopes),
    )
    # stdio builds its own server rather than sharing the HTTP one: this is a
    # dedicated process, and run_stdio_async manages its own session lifecycle.
    mcp = build_server()
    await mcp.run_stdio_async()
    return 0


def main() -> int:
    """Console entry point: ``axiom-mcp``."""

    try:
        return asyncio.run(_serve_stdio())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
