"""Gateway authentication and rate limiting."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from axiom.config import get_settings
from axiom.db import session_scope
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(gateway_client: AsyncClient) -> None:
    r = await gateway_client.post("/v1/openai/chat/completions", json={"model": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(gateway_client: AsyncClient) -> None:
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": "Bearer axm_live_" + "z" * 64},
        json={"model": "x"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_revoked_api_key_returns_401(
    client: AsyncClient,
    gateway_client: AsyncClient,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    from tests.conftest import auth_headers

    h = auth_headers(fx["user_access"])
    revoke = await client.delete(
        f"/api/v1/projects/{fx['project_id']}/api-keys/{fx['api_key_id']}",
        headers=h,
    )
    assert revoke.status_code == 200
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "x"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_valid_api_key_passes_auth(
    client: AsyncClient,
    gateway_client: AsyncClient,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4", "messages": []},
    )
    assert r.status_code != 401


@pytest.mark.asyncio
async def test_project_resolved_from_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as db:
        from axiom.services.api_key.service import verify_key

        ctx = await verify_key(db, fx["api_key_full"], required_scope="govern:write")
        assert ctx is not None
        assert str(ctx.project_id) == fx["project_id"]


@pytest.mark.asyncio
async def test_rate_limit_returns_429(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    monkeypatch.setenv("AXIOM_GATEWAY_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    auth = {"Authorization": f"Bearer {fx['api_key_full']}"}
    for _ in range(2):
        await gateway_client.post(
            "/v1/openai/chat/completions",
            headers=auth,
            json={"model": "x"},
        )
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers=auth,
        json={"model": "x"},
    )
    assert r.status_code == 429
