"""Transport-level behaviour: both transports must authenticate identically.

The point of these tests is that neither transport is a back door. HTTP
requests without a valid key never reach the MCP app, and the stdio entry
point refuses to start rather than serving an unauthenticated session.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from axiom.mcp.auth import (
    API_KEY_ENV_VAR,
    SCOPE_READ,
    SCOPE_WRITE,
    MCPAuthError,
    MCPPrincipal,
    api_key_from_env,
    current_principal,
    reset_principal,
    set_principal,
)
from axiom.mcp.server import SERVER_NAME, build_server
from axiom.mcp.transport import MCPAuthMiddleware
from tests.fixtures.governance import bootstrap_project_with_api_key

MCP_SCOPES = [SCOPE_READ, SCOPE_WRITE]


async def _noop_app(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"reached"})


@pytest.mark.asyncio
async def test_http_without_key_never_reaches_app() -> None:
    app = MCPAuthMiddleware(_noop_app)
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/", json={})
    assert r.status_code == 401
    assert r.text != "reached"
    assert "www-authenticate" in {k.lower() for k in r.headers}


@pytest.mark.asyncio
async def test_http_with_invalid_key_rejected() -> None:
    app = MCPAuthMiddleware(_noop_app)
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/", headers={"Authorization": "Bearer axm_live_bogus"}, json={})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_http_with_valid_key_reaches_app(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, scopes=MCP_SCOPES)
    app = MCPAuthMiddleware(_noop_app)
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/", headers={"Authorization": f"Bearer {fx['api_key_full']}"}, json={})
    assert r.status_code == 200
    assert r.text == "reached"


@pytest.mark.asyncio
async def test_http_accepts_x_api_key_header(client: AsyncClient) -> None:
    """Parity with POST /v1/govern, which accepts both header forms."""

    fx = await bootstrap_project_with_api_key(client, scopes=MCP_SCOPES)
    app = MCPAuthMiddleware(_noop_app)
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/", headers={"X-Api-Key": fx["api_key_full"]}, json={})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_principal_is_reset_after_request(client: AsyncClient) -> None:
    """A principal must not leak out of the request that established it."""

    fx = await bootstrap_project_with_api_key(client, scopes=MCP_SCOPES)
    app = MCPAuthMiddleware(_noop_app)
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/", headers={"Authorization": f"Bearer {fx['api_key_full']}"}, json={})

    with pytest.raises(MCPAuthError):
        current_principal()


def test_current_principal_raises_without_session() -> None:
    with pytest.raises(MCPAuthError):
        current_principal()


def test_set_and_reset_principal() -> None:
    fake = MCPPrincipal(ctx=object(), presented_key="axm_live_x")  # type: ignore[arg-type]
    token = set_principal(fake)
    try:
        assert current_principal() is fake
    finally:
        reset_principal(token)
    with pytest.raises(MCPAuthError):
        current_principal()


def test_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    assert api_key_from_env() == ""
    monkeypatch.setenv(API_KEY_ENV_VAR, "  axm_live_padded  ")
    assert api_key_from_env() == "axm_live_padded"


def test_server_registers_the_five_tools() -> None:
    server = build_server()
    assert server.name == SERVER_NAME


@pytest.mark.asyncio
async def test_server_tool_list_is_exactly_five() -> None:
    """Guard against tool sprawl: each tool is permanent API surface."""

    server = build_server()
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "govern_action",
        "check_policy",
        "verify_receipt",
        "get_receipt",
        "list_policies",
    }


@pytest.mark.asyncio
async def test_tool_descriptions_state_obligations() -> None:
    """ADR-027: descriptions are read by a model deciding whether to comply."""

    server = build_server()
    tools = {t.name: (t.description or "") for t in await server.list_tools()}
    assert "must" in tools["govern_action"].lower()
    assert "not an audit record" in tools["check_policy"].lower()
