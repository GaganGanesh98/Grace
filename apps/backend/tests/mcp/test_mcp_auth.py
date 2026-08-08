"""MCP session authentication and scope enforcement.

These tests exercise the auth layer directly rather than through a live MCP
client, because the property under test is "no tool executes without a
resolved, correctly-scoped principal" — which is enforced in `axiom.mcp.auth`
and asserted by the tool handlers, not by the protocol framing.
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from axiom.db import session_scope
from axiom.mcp import schemas
from axiom.mcp.auth import (
    SCOPE_READ,
    SCOPE_WRITE,
    MCPAuthError,
    extract_bearer,
    resolve_principal,
    reverify_for_write,
)
from axiom.mcp.tools import check_policy, govern_action
from axiom.models.api_key import ApiKey
from tests.fixtures.governance import bootstrap_project_with_api_key

MCP_SCOPES = [SCOPE_READ, SCOPE_WRITE]
_APPROVE_RULES = [
    {"id": "ok", "description": "allow chat", "when": {"type": "chat"}, "then": "approve"}
]


@pytest.mark.asyncio
async def test_valid_key_resolves_to_principal(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, scopes=MCP_SCOPES)
    async with session_scope() as db:
        principal = await resolve_principal(db, fx["api_key_full"])
    assert str(principal.ctx.project_id) == fx["project_id"]
    assert SCOPE_WRITE in principal.scopes


@pytest.mark.asyncio
async def test_missing_key_rejected() -> None:
    async with session_scope() as db:
        with pytest.raises(MCPAuthError):
            await resolve_principal(db, "")


@pytest.mark.asyncio
async def test_garbage_key_rejected() -> None:
    async with session_scope() as db:
        with pytest.raises(MCPAuthError):
            await resolve_principal(db, "not-a-grace-key")


@pytest.mark.asyncio
async def test_revoked_key_rejected(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, scopes=MCP_SCOPES)
    async with session_scope() as db:
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == fx["api_key_id"])
            .values(revoked_at=dt.datetime.now(dt.UTC))
        )
        await db.commit()
    async with session_scope() as db:
        with pytest.raises(MCPAuthError):
            await resolve_principal(db, fx["api_key_full"])


@pytest.mark.asyncio
async def test_read_only_key_cannot_govern(client: AsyncClient) -> None:
    """A key with mcp:read must not be able to seal a receipt."""

    fx = await bootstrap_project_with_api_key(
        client, policy_rules=_APPROVE_RULES, scopes=[SCOPE_READ]
    )
    async with session_scope() as db:
        principal = await resolve_principal(db, fx["api_key_full"])
        payload = schemas.GovernActionInput.model_validate(
            {"action": {"type": "chat"}, "agent_id": fx["agent_id"]}
        )
        with pytest.raises(MCPAuthError):
            await govern_action(db, principal, payload)


@pytest.mark.asyncio
async def test_govern_write_scope_does_not_grant_mcp(client: AsyncClient) -> None:
    """ADR-026: an HTTP API key is not implicitly an MCP credential."""

    fx = await bootstrap_project_with_api_key(
        client, policy_rules=_APPROVE_RULES, scopes=["govern:write"]
    )
    async with session_scope() as db:
        principal = await resolve_principal(db, fx["api_key_full"])
        payload = schemas.GovernActionInput.model_validate(
            {"action": {"type": "chat"}, "agent_id": fx["agent_id"]}
        )
        with pytest.raises(MCPAuthError):
            await govern_action(db, principal, payload)
        with pytest.raises(MCPAuthError):
            await check_policy(db, principal, schemas.CheckPolicyInput(action={"type": "chat"}))


@pytest.mark.asyncio
async def test_revocation_takes_effect_mid_session(client: AsyncClient) -> None:
    """A long-lived session must stop writing the moment its key is revoked."""

    fx = await bootstrap_project_with_api_key(
        client, policy_rules=_APPROVE_RULES, scopes=MCP_SCOPES
    )
    async with session_scope() as db:
        principal = await resolve_principal(db, fx["api_key_full"])

    # Principal is already resolved — as it would be in a live session.
    async with session_scope() as db:
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == fx["api_key_id"])
            .values(revoked_at=dt.datetime.now(dt.UTC))
        )
        await db.commit()

    async with session_scope() as db:
        with pytest.raises(MCPAuthError):
            await reverify_for_write(db, principal)


def test_extract_bearer_prefers_authorization_header() -> None:
    assert extract_bearer({"Authorization": "Bearer axm_live_abc"}) == "axm_live_abc"
    assert extract_bearer({"authorization": "bearer axm_live_abc"}) == "axm_live_abc"


def test_extract_bearer_falls_back_to_x_api_key() -> None:
    assert extract_bearer({"X-Api-Key": "axm_live_xyz"}) == "axm_live_xyz"
    assert extract_bearer({}) == ""
