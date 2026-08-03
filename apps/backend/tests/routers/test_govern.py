"""/v1/govern contract tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.asyncio
async def test_govern_requires_api_key(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/govern",
        json={"action": {"type": "ping"}, "agent_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_govern_valid_request_returns_receipt(client: AsyncClient) -> None:
    rules = [
        {
            "id": "allow",
            "description": "Allow it",
            "when": {"type": "chat"},
            "then": "approve",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "action": {"type": "chat", "body": "hi"},
            "agent_id": fx["agent_id"],
            "mode": "enforce",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["receipt_id"].startswith("rcpt_")
    assert data["verdict"] == "approve"
    assert data["merkle_leaf_index"] == 0
    assert data["merkle_tree_size"] == 1
    assert data["dispatched"] is True
    assert data["verify_url"].endswith(f"/v1/verify/{data['receipt_id']}")


@pytest.mark.asyncio
async def test_govern_deny_enforce_blocks(client: AsyncClient) -> None:
    rules = [
        {
            "id": "block_email",
            "description": "Block outbound email",
            "when": {"type": "send_email"},
            "then": "deny",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "action": {"type": "send_email", "to": "x"},
            "agent_id": fx["agent_id"],
            "mode": "enforce",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"] == "deny"
    assert data["dispatched"] is False


@pytest.mark.asyncio
async def test_govern_shadow_never_dispatches(client: AsyncClient) -> None:
    rules = [{"id": "x", "description": "ok", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "action": {"type": "t"},
            "agent_id": fx["agent_id"],
            "mode": "shadow",
        },
    )
    assert r.status_code == 200
    assert r.json()["dispatched"] is False
    assert r.json()["verdict"] == "approve"


@pytest.mark.asyncio
async def test_govern_rejects_invalid_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.post(
        "/v1/govern",
        headers=_auth("axm_live_" + "q" * 40),
        json={
            "action": {"type": "t"},
            "agent_id": fx["agent_id"],
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_govern_body_size_limit_enforced(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    big_body = "x" * (101 * 1024)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "action": {"type": "t", "body": big_body},
            "agent_id": fx["agent_id"],
        },
    )
    # Either our route-specific 413 (preferred) or the global body-size middleware.
    assert r.status_code in (413, 422)


@pytest.mark.asyncio
async def test_govern_schema_forbids_extras(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "action": {"type": "t"},
            "agent_id": fx["agent_id"],
            "mode": "enforce",
            "extra": "nope",
        },
    )
    assert r.status_code == 422
