"""Vault HTTP API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.mark.asyncio
async def test_create_vault_key_returns_masked(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    r = await client.post(
        "/api/v1/vault",
        headers=h,
        json={
            "raw_key": "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789",
            "name": "Prod",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789" not in r.text
    assert data["key_prefix"]
    assert data["key_suffix"]
    assert data["service"] == "openai"
    assert data["kind"] == "llm"


@pytest.mark.asyncio
async def test_list_vault_keys_returns_masked(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    await client.post(
        "/api/v1/vault",
        headers=h,
        json={
            "raw_key": "sk-proj-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "name": "A",
        },
    )
    r = await client.get("/api/v1/vault", headers=h)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert "sk-proj-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in r.text


@pytest.mark.asyncio
async def test_delete_vault_key_succeeds(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    c = await client.post(
        "/api/v1/vault",
        headers=h,
        json={
            "raw_key": "sk-proj-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "name": "B",
        },
    )
    kid = c.json()["id"]
    d = await client.delete(f"/api/v1/vault/{kid}", headers=h)
    assert d.status_code == 200
    assert d.json()["deleted"] is True
    assert d.json()["id"] == kid


@pytest.mark.asyncio
async def test_member_can_create_own_vault_key(client: AsyncClient) -> None:
    from tests.conftest import signup_user, unique_email, unique_slug

    owner_email = unique_email()
    member_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    member_t = await signup_user(client, member_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "VaultRole", "slug": unique_slug("vault-role")},
    )
    pid = project.json()["data"]["id"]
    inv = await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": member_email, "role": "MEMBER"},
    )
    assert inv.status_code == 201
    r = await client.post(
        "/api/v1/vault",
        headers=auth_headers(member_t["access_token"]),
        json={
            "raw_key": "sk-proj-cccccccccccccccccccccccccccccccc",
            "name": "C",
        },
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_auto_detect_openai_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    r = await client.post(
        "/api/v1/vault",
        headers=h,
        json={
            "raw_key": "sk-proj-dddddddddddddddddddddddddddddddd",
            "name": "D",
        },
    )
    assert r.status_code == 201
    assert r.json()["detected_service"] == "openai"


@pytest.mark.asyncio
async def test_auto_detect_anthropic_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    r = await client.post(
        "/api/v1/vault",
        headers=h,
        json={
            "raw_key": "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx",
            "name": "E",
        },
    )
    assert r.status_code == 201
    assert r.json()["detected_service"] == "anthropic"
