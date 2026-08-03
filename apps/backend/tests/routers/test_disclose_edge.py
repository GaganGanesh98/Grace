"""Edge paths for /v1/disclose: date inversion, unsigned receipt, key mismatch."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from axiom.db import session_scope
from axiom.models.receipt import Receipt
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.asyncio
async def test_disclose_from_date_after_to_date_rejected(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2030-01-01T00:00:00Z",
            "to_date": "2026-01-01T00:00:00Z",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_disclose_agent_id_filter(client: AsyncClient) -> None:
    rules = [{"id": "x", "description": "ok", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    # One receipt under our agent; disclose with a different agent_id should return 0.
    r0 = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r0.status_code == 200
    bogus = "00000000-0000-0000-0000-000000000000"
    r = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
            "agent_id": bogus,
        },
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_disclose_skips_unsigned_receipts(client: AsyncClient) -> None:
    rules = [{"id": "x", "description": "ok", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    rid = r.json()["receipt_id"]
    async with session_scope() as session:
        await session.execute(
            update(Receipt).where(Receipt.id == rid).values(merkle_root=None, merkle_tree_size=None)
        )
    r2 = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
        },
    )
    assert r2.status_code == 200
    # total counts all executions for the period; returned receipts excludes the unsigned one.
    body = r2.json()
    assert body["total"] >= 1
    assert all(r_item["receipt_id"] != rid for r_item in body["receipts"])


@pytest.mark.asyncio
async def test_disclose_evidence_decryption_failure_surfaces_as_error(
    client: AsyncClient,
) -> None:
    """Tampered ciphertext triggers the decrypt-failed branch (evidence={error:...})."""

    rules = [{"id": "x", "description": "ok", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    rid = r.json()["receipt_id"]
    async with session_scope() as session:
        row = await session.get(Receipt, rid)
        assert row is not None
        tampered = bytearray(row.evidence_ciphertext)
        tampered[0] ^= 0xFF
        await session.execute(
            update(Receipt).where(Receipt.id == rid).values(evidence_ciphertext=bytes(tampered))
        )

    r2 = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
        },
    )
    body = r2.json()
    target = next(item for item in body["receipts"] if item["receipt_id"] == rid)
    assert target["evidence"]["decrypted"] is False
    assert target["evidence"].get("error") == "decryption_failed"
