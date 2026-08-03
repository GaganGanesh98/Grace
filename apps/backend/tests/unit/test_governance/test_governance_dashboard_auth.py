"""Unified JWT + API key auth for dashboard-facing governance endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key

G_PREFIX = "/v1/governance"
C_PREFIX = "/v1/chains"


@pytest.mark.asyncio
async def test_chains_accessible_with_jwt(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.get(
        C_PREFIX,
        headers=auth_headers(fx["user_access"]),
        params={"project_id": fx["project_id"], "page": 1, "per_page": 10},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_chains_accessible_with_api_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.get(
        C_PREFIX,
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        params={"page": 1, "per_page": 10},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_chains_rejects_no_auth(client: AsyncClient) -> None:
    r = await client.get(C_PREFIX, params={"page": 1, "per_page": 10})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_receipt_accessible_with_jwt(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    g = await client.post(
        f"{G_PREFIX}/govern",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={
            "agent_id": "jwt-rcpt",
            "action_type": "tool.http.get",
            "target": "https://jwt-receipt.example",
            "risk": "low",
        },
    )
    assert g.status_code == 200, g.text
    rid = g.json()["receipt_id"]
    r = await client.get(
        f"{G_PREFIX}/receipts/{rid}",
        headers=auth_headers(fx["user_access"]),
        params={"project_id": fx["project_id"]},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_govern_rejects_jwt(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.post(
        f"{G_PREFIX}/govern",
        headers=auth_headers(fx["user_access"]),
        json={
            "agent_id": "no-jwt",
            "action_type": "tool.http.get",
            "target": "https://nj.example",
            "risk": "low",
        },
    )
    assert r.status_code == 401
