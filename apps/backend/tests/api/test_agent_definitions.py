"""Phase 6.5 — /v1/agent-definitions API (Batch B registers routes).

These tests are RED until routers + services land: they assert the HTTP surface exists.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_list_agent_definitions_not_404(client: AsyncClient) -> None:
    """Batch B: GET /v1/agent-definitions (dual auth) must be registered."""
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    r = await client.get("/v1/agent-definitions", headers=h)
    assert r.status_code != 404, r.text


@pytest.mark.asyncio
async def test_reject_unsupported_vault_provider_on_create(client: AsyncClient) -> None:
    """Unsupported vault provider → 400 with clear message (Batch B)."""
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "AD", "slug": unique_slug("ad-proj")},
    )
    assert project.status_code == 201, project.text
    pid = project.json()["data"]["id"]
    # Replicate-style key prefix → provider "replicate" (see axiom.gateway.provider_registry)
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "r8_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "name": "rep"},
    )
    assert vk.status_code == 201, vk.text
    vault_key_id = vk.json()["id"]

    body = {
        "name": "def-replicate",
        "model": "any",
        "vault_key_id": vault_key_id,
        "system_prompt": "hi",
        "tools_config": {},
    }
    r = await client.post(f"/v1/agent-definitions?project_id={pid}", headers=h, json=body)
    assert r.status_code == 400
    err = r.json()
    detail = err.get("detail", err)
    assert isinstance(detail, (str, dict))
    text_blob = str(detail)
    assert "replicate" in text_blob.lower() or "not yet supported" in text_blob.lower()


@pytest.mark.asyncio
async def test_create_agent_definition_not_404(client: AsyncClient) -> None:
    """Batch B: POST /v1/agent-definitions returns 201 when valid (not 404)."""
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "AD2", "slug": unique_slug("ad2-proj")},
    )
    assert project.status_code == 201, project.text
    pid = project.json()["data"]["id"]
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "a" * 40, "name": "oai"},
    )
    assert vk.status_code == 201, vk.text
    vault_key_id = vk.json()["id"]
    r = await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "my-bot",
            "model": "gpt-4o",
            "vault_key_id": vault_key_id,
            "system_prompt": "You are a test agent.",
            "tools_config": {},
        },
    )
    assert r.status_code != 404, r.text
