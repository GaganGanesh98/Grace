"""APIKey verification service tests."""

from __future__ import annotations

import hashlib
import inspect

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.services.api_key import service as api_key_service
from axiom.services.api_key.service import verify_key
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.mark.asyncio
async def test_verify_valid_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        ctx = await verify_key(session, fx["api_key_full"])
    assert ctx is not None
    assert str(ctx.project_id) == fx["project_id"]
    assert "govern:write" in ctx.scopes


@pytest.mark.asyncio
async def test_verify_unknown_key_returns_none(client: AsyncClient) -> None:
    await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        ctx = await verify_key(session, "axm_live_" + "z" * 64)
    assert ctx is None


@pytest.mark.asyncio
async def test_verify_rejects_malformed(client: AsyncClient) -> None:
    async with session_scope() as session:
        assert await verify_key(session, "") is None
        assert await verify_key(session, "not_an_axm_key") is None
        assert await verify_key(session, "axm_live_") is None  # too short


@pytest.mark.asyncio
async def test_verify_rejects_revoked_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    from tests.conftest import auth_headers

    h = auth_headers(fx["user_access"])
    revoke = await client.delete(
        f"/api/v1/projects/{fx['project_id']}/api-keys/{fx['api_key_id']}",
        headers=h,
    )
    assert revoke.status_code == 200
    async with session_scope() as session:
        ctx = await verify_key(session, fx["api_key_full"])
    assert ctx is None


@pytest.mark.asyncio
async def test_verify_scope_check(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        ok = await verify_key(session, fx["api_key_full"], required_scope="govern:write")
        assert ok is not None
        missing = await verify_key(session, fx["api_key_full"], required_scope="receipts:admin")
        assert missing is None


def test_verify_uses_constant_time_compare() -> None:
    src = inspect.getsource(api_key_service)
    assert "hmac.compare_digest" in src
    assert "key_hash ==" not in src


@pytest.mark.asyncio
async def test_verify_ignores_wrong_prefix(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    # Swap the prefix; sha256 of the mutated string won't match.
    mutated = "axm_test_" + fx["api_key_full"][len("axm_live_") :]
    async with session_scope() as session:
        ctx = await verify_key(session, mutated)
    assert ctx is None


@pytest.mark.asyncio
async def test_verify_hash_check(client: AsyncClient) -> None:
    """Smoke-check the hash-based identity: tampering a single char => None."""
    fx = await bootstrap_project_with_api_key(client)
    full = fx["api_key_full"]
    bad = full[:-1] + ("A" if full[-1] != "A" else "B")
    # confirm the hash actually changes
    assert hashlib.sha256(full.encode()).hexdigest() != hashlib.sha256(bad.encode()).hexdigest()
    async with session_scope() as session:
        ctx = await verify_key(session, bad)
    assert ctx is None
