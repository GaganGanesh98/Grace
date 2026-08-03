"""HTTP contract tests for /v1/preflight."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.asyncio
async def test_preflight_without_content_length_header(client: AsyncClient) -> None:
    """httpx normally sets Content-Length; ensure the route tolerates its absence."""

    rules = [{"id": "a", "description": "d", "when": {"type": "nocl"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    req = client.build_request(
        "POST",
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "nocl"}, "agent_id": fx["agent_id"]},
    )
    if "content-length" in req.headers:
        del req.headers["content-length"]
    r = await client.send(req)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_preflight_requires_api_key(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/preflight",
        json={"action": {"type": "ping"}, "agent_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_preflight_invalid_action_returns_400(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    raw = (
        '{"action":{"type":"t","v":Infinity},"agent_id":"' + fx["agent_id"] + '","mode":"enforce"}'
    )
    r = await client.post(
        "/v1/preflight",
        headers={**_auth(fx["api_key_full"]), "content-type": "application/json"},
        content=raw.encode(),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_preflight_valid_request_returns_prediction(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "chat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "chat"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["prediction_id"].startswith("pred_")
    assert data["predicted_verdict"] == "approve"
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_preflight_does_not_emit_receipt(client: AsyncClient) -> None:
    from sqlalchemy import func, select

    from axiom.db import session_scope
    from axiom.models.execution import Execution
    from axiom.models.merkle_node import MerkleNode
    from axiom.models.receipt import Receipt

    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async def counts() -> tuple[int, int, int]:
        async with session_scope() as session:
            e = await session.scalar(select(func.count()).select_from(Execution))
            r = await session.scalar(select(func.count()).select_from(Receipt))
            m = await session.scalar(select(func.count()).select_from(MerkleNode))
        return int(e or 0), int(r or 0), int(m or 0)

    before = await counts()
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    assert before == await counts()


@pytest.mark.asyncio
async def test_preflight_invalid_content_length_returns_400(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/preflight",
        headers={
            **_auth(fx["api_key_full"]),
            "content-length": "not-an-int",
        },
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_preflight_body_size_limit_enforced(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/preflight",
        headers={
            **_auth(fx["api_key_full"]),
            "content-length": str(200 * 1024),
        },
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_preflight_response_includes_disclaimer(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    assert "cryptographic receipt" in r.json()["disclaimer"]
