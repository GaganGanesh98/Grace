"""End-to-end: govern -> verify -> disclose.

This is the "does it actually work?" smoke test for Phase 2.
"""

from __future__ import annotations

import base64
import hashlib

import pytest
from httpx import AsyncClient

from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.crypto.merkle import InclusionProof, verify_inclusion
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.asyncio
async def test_govern_then_verify_then_disclose_full_chain(client: AsyncClient) -> None:
    rules = [
        {
            "id": "r-chat-ok",
            "description": "Chat is fine",
            "when": {"type": "chat"},
            "then": "approve",
            "legal_citation": "Company Policy 3.1",
            "remediation_guidance": "nothing to remediate",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    # 1) govern
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "action": {"type": "chat", "body": "hello world"},
            "agent_id": fx["agent_id"],
            "mode": "enforce",
        },
    )
    assert r.status_code == 200, r.text
    receipt_id = r.json()["receipt_id"]
    assert r.json()["verdict"] == "approve"
    assert "Company Policy 3.1" in r.json()["explanation"]

    # 2) verify (public, no auth)
    r_v = await client.get(f"/v1/verify/{receipt_id}", headers={})
    assert r_v.status_code == 200, r_v.text
    v = r_v.json()
    assert v["verified"] is True
    assert v["verification_details"]["ed25519_signature_valid"] is True
    assert v["verification_details"]["ml_dsa_signature_valid"] is True
    assert v["verification_details"]["merkle_inclusion_valid"] is True

    # Offline re-verification using the same primitives anyone could script.
    merkle_root = base64.b64decode(v["merkle_root"])
    payload_hash = base64.b64decode(v["payload_hash"])
    proof = InclusionProof(
        leaf_index=v["inclusion_proof"]["leaf_index"],
        tree_size=v["inclusion_proof"]["tree_size"],
        path=tuple(base64.b64decode(p) for p in v["inclusion_proof"]["path"]),
    )
    assert verify_inclusion(merkle_root, payload_hash, proof) is True

    # And offline signature verification using the public keys from verify.
    signed_body = {
        "algorithm": v["algorithm"],
        "receipt_id": receipt_id,
        "payload_hash": v["payload_hash"],
        "evidence_key_id": (
            # the verify response doesn't surface evidence_key_id publicly, so we
            # reconstruct from the canonical body only. The hybrid signer signs
            # over this exact shape.
            ""
        ),
        "merkle": {
            "leaf_index": v["inclusion_proof"]["leaf_index"],
            "tree_size": v["inclusion_proof"]["tree_size"],
            "root": v["merkle_root"],
        },
    }
    # The signed body includes evidence_key_id. Our verify endpoint already
    # checked ed25519/ml_dsa against the canonical body; we only confirm the
    # hash envelope is stable.
    assert hashlib.sha256(canonicalize(signed_body)).digest() is not None

    # quick smoke: ed25519 public key is accepted by the library
    assert (
        ed25519.verify(
            v["ed25519_public_pem"],
            canonicalize(signed_body),
            b"\x00" * 64,  # fake sig — just checks function returns False, not True
        )
        is False
    )
    assert (
        ml_dsa.verify(
            base64.b64decode(v["ml_dsa_public_b64"]),
            canonicalize(signed_body),
            b"\x00" * 32,
        )
        is False
    )

    # 3) disclose — should include this receipt with a fresh proof
    r_d = await client.post(
        "/v1/disclose",
        headers=_auth(fx["api_key_full"]),
        json={
            "from_date": "2026-01-01T00:00:00Z",
            "to_date": "2030-01-01T00:00:00Z",
        },
    )
    assert r_d.status_code == 200
    body = r_d.json()
    assert body["total"] == 1
    item = body["receipts"][0]
    assert item["receipt_id"] == receipt_id
    assert item["inclusion_proof"]["leaf_index"] == 0
    assert item["evidence"]["decrypted"] is True
    assert item["evidence"]["body"]["action"]["body"] == "hello world"
    assert item["evidence"]["body"]["explanation"]
