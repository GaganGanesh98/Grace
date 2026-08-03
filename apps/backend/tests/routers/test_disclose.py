"""/v1/disclose contract tests + cross-project leak prevention."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


async def _seed_receipts(client: AsyncClient, api_key: str, agent_id: str, count: int) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        r = await client.post(
            "/v1/govern",
            headers=_auth(api_key),
            json={
                "action": {"type": "chat", "body": f"msg-{i}"},
                "agent_id": agent_id,
            },
        )
        assert r.status_code == 200, r.text
        ids.append(r.json()["receipt_id"])
    return ids


@pytest.mark.asyncio
async def test_disclose_requires_api_key(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/disclose",
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2026-12-31T23:59:59Z",
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_disclose_returns_receipts_with_proofs(client: AsyncClient) -> None:
    rules = [{"id": "x", "description": "ok", "when": {"type": "chat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    await _seed_receipts(client, fx["api_key_full"], fx["agent_id"], 3)

    r = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 3
    assert len(body["receipts"]) == body["total"]
    for item in body["receipts"]:
        assert item["inclusion_proof"]["tree_size"] >= 1
        assert item["merkle_root"]
        assert item["evidence"]["decrypted"] is True
        assert item["evidence"]["body"]["action"]["type"] == "chat"


@pytest.mark.asyncio
async def test_disclose_scoped_to_api_key_project(client: AsyncClient) -> None:
    """Cross-project leak check: API key A cannot see project B's receipts."""

    rules = [{"id": "x", "description": "ok", "when": {"type": "chat"}, "then": "approve"}]
    a = await bootstrap_project_with_api_key(client, policy_rules=rules)
    b = await bootstrap_project_with_api_key(client, policy_rules=rules)

    await _seed_receipts(client, a["api_key_full"], a["agent_id"], 2)
    await _seed_receipts(client, b["api_key_full"], b["agent_id"], 4)

    r = await client.post(
        "/v1/disclose",
        headers=_auth(a["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2  # only A's
    for item in body["receipts"]:
        assert item["evidence"]["body"]["project_id"] == a["project_id"]


@pytest.mark.asyncio
async def test_disclose_date_filter(client: AsyncClient) -> None:
    rules = [{"id": "x", "description": "ok", "when": {"type": "chat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    await _seed_receipts(client, fx["api_key_full"], fx["agent_id"], 2)

    r = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "1970-01-01T00:00:00Z",
            "to_date": "1999-12-31T23:59:59Z",
        },
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_disclose_action_type_filter(client: AsyncClient) -> None:
    rules = [
        {"id": "a", "description": "a", "when": {"type": "chat"}, "then": "approve"},
        {"id": "b", "description": "b", "when": {"type": "email"}, "then": "approve"},
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    await _seed_receipts(client, fx["api_key_full"], fx["agent_id"], 2)
    # seed one email action
    r_email = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "email", "body": "hi"}, "agent_id": fx["agent_id"]},
    )
    assert r_email.status_code == 200

    r = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
            "action_type": "email",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["receipts"][0]["evidence"]["body"]["action"]["type"] == "email"


@pytest.mark.asyncio
async def test_disclose_per_page_capped(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
            "per_page": 500,
        },
    )
    assert r.status_code == 422
