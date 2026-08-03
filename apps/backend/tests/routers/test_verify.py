"""/v1/verify contract tests (public, no auth)."""

from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from axiom.db import session_scope
from axiom.models.receipt import Receipt
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


async def _mint_receipt(client: AsyncClient) -> tuple[str, str]:
    rules = [{"id": "x", "description": "ok", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200, r.text
    return r.json()["receipt_id"], fx["api_key_full"]


@pytest.mark.asyncio
async def test_verify_unknown_receipt_returns_404(client: AsyncClient) -> None:
    r = await client.get("/v1/verify/rcpt_does_not_exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_verify_returns_valid_receipt(client: AsyncClient) -> None:
    receipt_id, _ = await _mint_receipt(client)
    r = await client.get(f"/v1/verify/{receipt_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is True
    assert body["verification_details"]["ed25519_signature_valid"] is True
    assert body["verification_details"]["ml_dsa_signature_valid"] is True
    assert body["verification_details"]["merkle_inclusion_valid"] is True
    assert body["inclusion_proof"]["leaf_index"] == 0
    assert body["verdict"] == "approve"


@pytest.mark.asyncio
async def test_verify_does_not_leak_evidence_ciphertext(client: AsyncClient) -> None:
    receipt_id, _ = await _mint_receipt(client)
    r = await client.get(f"/v1/verify/{receipt_id}")
    body = r.json()
    # Response must NOT contain evidence ciphertext/nonce fields.
    assert "evidence_ciphertext" not in body
    assert "evidence_nonce" not in body
    assert "evidence" not in body


@pytest.mark.asyncio
async def test_verify_does_not_require_auth(client: AsyncClient) -> None:
    receipt_id, _ = await _mint_receipt(client)
    r = await client.get(f"/v1/verify/{receipt_id}", headers={})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_verify_detects_tampered_receipt(client: AsyncClient) -> None:
    receipt_id, _ = await _mint_receipt(client)
    # Flip a single byte of the payload_hash in the DB.
    async with session_scope() as session:
        row = await session.get(Receipt, receipt_id)
        assert row is not None
        tampered = bytearray(row.payload_hash)
        tampered[0] ^= 0xFF
        await session.execute(
            update(Receipt).where(Receipt.id == receipt_id).values(payload_hash=bytes(tampered))
        )
    r = await client.get(f"/v1/verify/{receipt_id}")
    assert r.status_code == 200
    assert r.json()["verified"] is False


@pytest.mark.asyncio
async def test_verify_detects_tampered_signature(client: AsyncClient) -> None:
    receipt_id, _ = await _mint_receipt(client)
    async with session_scope() as session:
        row = await session.get(Receipt, receipt_id)
        assert row is not None
        tampered = bytearray(row.ed25519_signature)
        tampered[0] ^= 0xFF
        await session.execute(
            update(Receipt)
            .where(Receipt.id == receipt_id)
            .values(ed25519_signature=bytes(tampered))
        )
    r = await client.get(f"/v1/verify/{receipt_id}")
    body = r.json()
    assert body["verified"] is False
    assert body["verification_details"]["ed25519_signature_valid"] is False


@pytest.mark.asyncio
async def test_verify_surfaces_public_key_fingerprints(client: AsyncClient) -> None:
    receipt_id, _ = await _mint_receipt(client)
    r = await client.get(f"/v1/verify/{receipt_id}")
    body = r.json()
    assert "ed25519_key_id" in body
    assert "ml_dsa_key_id" in body
    # public PEM + b64 let anyone verify offline
    assert "BEGIN PUBLIC KEY" in body["ed25519_public_pem"]
    # decodable b64
    base64.b64decode(body["ml_dsa_public_b64"])
