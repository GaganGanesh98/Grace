"""HTTP surface for Phase 2.5 governance engine."""

from __future__ import annotations

import base64
import json
from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.models.project import Project
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.governance.receipt import approval_dict_from_receipt, unsigned_receipt_for_sealing
from axiom.services.receipt.keys import get_signing_keys
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


G_PREFIX = "/v1/governance"


@pytest.mark.asyncio
async def test_govern_unauthorized(client: AsyncClient) -> None:
    r = await client.post(
        f"{G_PREFIX}/govern",
        json={
            "agent_id": "a",
            "action_type": "t",
            "target": "https://x",
            "risk": "low",
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_govern_invalid_body_422(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    r = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "a",
            "action_type": "t",
            "target": "https://x",
            "risk": "not-a-tier",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_govern_report_get_verify_flow(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])

    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    gov = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "gov-api-agent",
            "action_type": "tool.http.get",
            "target": "https://finance.example.com/q",
            "risk": "low",
        },
    )
    assert gov.status_code == 200, gov.text
    receipt_id = gov.json()["receipt_id"]

    rep = await client.post(
        f"{G_PREFIX}/report",
        headers=_auth(fx["api_key_full"]),
        json={
            "receipt_id": receipt_id,
            "outcome": {
                "target": "https://finance.example.com/q",
                "action_type": "tool.http.get",
                "risk": "low",
            },
        },
    )
    assert rep.status_code == 200, rep.text
    body = rep.json()
    assert body["status"] == "sealed"
    assert body["signatures"]["ed25519"] is True
    assert body["signatures"]["ml_dsa_65"] is True

    got = await client.get(
        f"{G_PREFIX}/receipts/{receipt_id}",
        headers=_auth(fx["api_key_full"]),
    )
    assert got.status_code == 200, got.text
    full = got.json()
    assert full["intent"]["target"] == "https://finance.example.com/q"
    assert full["status"] == "sealed"

    keys = get_signing_keys()
    merkle = full["merkle"]

    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, UUID(receipt_id))
        intent = await session.get(GovernanceIntent, rec.intent_id) if rec else None
        verdict = await session.get(GovernanceVerdict, rec.verdict_id) if rec else None
        assert rec is not None and intent is not None and verdict is not None
        payload_obj = unsigned_receipt_for_sealing(
            receipt_id=str(rec.id),
            intent=intent,
            verdict=verdict,
            execution_data=rec.execution_data,
            verification_status=rec.verification or "",
            mismatches=list(rec.mismatches or []),
            executed_at=rec.executed_at,
            approval=approval_dict_from_receipt(rec),
        )

    canon = canonicalize(payload_obj)
    receipt_json = canon.decode("utf-8")

    vreq = {
        "receipt_json": receipt_json,
        "ed25519_signature": base64.b64encode(rec.ed25519_sig).decode("ascii"),
        "ml_dsa_signature": base64.b64encode(rec.ml_dsa_sig).decode("ascii"),
        "merkle_proof": merkle.get("path") or [],
        "merkle_root": merkle["root"],
        "ed25519_public_key": keys.ed25519_public,
        "ml_dsa_public_key": base64.b64encode(keys.ml_dsa_public).decode("ascii"),
        "leaf_index": merkle.get("leaf_index"),
        "tree_size": merkle.get("tree_size"),
    }
    vr = await client.post(f"{G_PREFIX}/verify", json=vreq)
    assert vr.status_code == 200, vr.text
    assert vr.json()["valid"] is True

    bad = json.loads(receipt_json)
    bad["v"] = 2
    vb = await client.post(
        f"{G_PREFIX}/verify",
        json={
            **vreq,
            "receipt_json": json.dumps(bad),
        },
    )
    assert vb.status_code == 200
    assert vb.json()["valid"] is False


@pytest.mark.asyncio
async def test_governance_verify_by_receipt_id_body(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])

    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    gov = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "verify-by-id",
            "action_type": "tool.http.get",
            "target": "https://finance.example.com/q",
            "risk": "low",
        },
    )
    assert gov.status_code == 200, gov.text
    receipt_id = gov.json()["receipt_id"]

    rep = await client.post(
        f"{G_PREFIX}/report",
        headers=_auth(fx["api_key_full"]),
        json={
            "receipt_id": receipt_id,
            "outcome": {
                "target": "https://finance.example.com/q",
                "action_type": "tool.http.get",
                "risk": "low",
            },
        },
    )
    assert rep.status_code == 200, rep.text

    vr = await client.post(
        f"{G_PREFIX}/verify",
        headers=_auth(fx["api_key_full"]),
        json={"receipt_id": receipt_id},
    )
    assert vr.status_code == 200, vr.text
    assert vr.json()["valid"] is True


@pytest.mark.asyncio
async def test_public_share_token_skips_api_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])

    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    gov = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "share-agent",
            "action_type": "t",
            "target": "https://s",
            "risk": "low",
            "metadata": {"public_share_token": "secret-token-xyz"},
        },
    )
    assert gov.status_code == 200
    rid = gov.json()["receipt_id"]

    await client.post(
        f"{G_PREFIX}/report",
        headers=_auth(fx["api_key_full"]),
        json={"receipt_id": rid, "outcome": {"target": "https://s", "action_type": "t"}},
    )

    r = await client.get(f"{G_PREFIX}/receipts/{rid}?share_token=secret-token-xyz")
    assert r.status_code == 200
    assert r.json()["id"] == rid
