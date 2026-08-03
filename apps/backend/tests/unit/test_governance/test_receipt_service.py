"""Receipt sealing: canonical payload, signatures, Merkle inclusion."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceReceipt
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.crypto.merkle import InclusionProof, verify_inclusion
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
from axiom.services.governance.receipt import (
    approval_dict_from_receipt,
    create_pending_receipt,
    reset_governance_merkle_for_tests,
    seal_receipt,
    unsigned_receipt_for_sealing,
)
from axiom.services.governance.verdict import render_verdict
from axiom.services.governance.verification import verify_execution
from axiom.services.receipt.keys import get_signing_keys
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_unsigned_receipt_payload_canonical_json_is_deterministic(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="canon",
            action_type="tool.http.get",
            target="https://example.com/a",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        raw = unsigned_receipt_for_sealing(
            receipt_id=str(uuid4()),
            intent=intent,
            verdict=verdict,
            execution_data={"target": intent.target},
            verification_status="pass",
            mismatches=[],
            executed_at=datetime.now(UTC),
            approval=None,
        )
        c1 = canonicalize(raw)
        c2 = canonicalize(raw)
        assert c1 == c2


@pytest.mark.asyncio
async def test_receipt_creation_and_seal_ed25519_ml_dsa_and_merkle(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="seal-svc",
            action_type="tool.http.get",
            target="https://api.example.com/z",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        outcome = {
            "target": intent.target,
            "action_type": intent.action_type,
            "risk": intent.risk_declared,
        }
        vres = verify_execution(intent, outcome)
        sealed = await seal_receipt(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=outcome,
            executed_at=datetime.now(UTC),
            verification_result=vres,
        )
        keys = get_signing_keys()
        msg = canonicalize(
            unsigned_receipt_for_sealing(
                receipt_id=str(sealed.id),
                intent=intent,
                verdict=verdict,
                execution_data=outcome,
                verification_status=vres.status,
                mismatches=list(vres.mismatches),
                executed_at=sealed.executed_at,
                approval=approval_dict_from_receipt(sealed),
            )
        )
        assert ed25519.verify(keys.ed25519_public, msg, sealed.ed25519_sig)
        assert ml_dsa.verify(keys.ml_dsa_public, msg, sealed.ml_dsa_sig)
        proof = sealed.merkle_proof
        assert isinstance(proof, dict)
        pobj = InclusionProof(
            leaf_index=int(proof["leaf_index"]),
            tree_size=int(proof["tree_size"]),
            path=tuple(bytes.fromhex(h) for h in proof["path"]),
        )
        assert verify_inclusion(sealed.merkle_root, sealed.receipt_hash, pobj)


@pytest.mark.asyncio
async def test_unsigned_payload_omits_approval_when_pending_or_absent(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="a",
            action_type="t",
            target="https://x",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        receipt.approval_status = "pending"
        raw = unsigned_receipt_for_sealing(
            receipt_id=str(receipt.id),
            intent=intent,
            verdict=verdict,
            execution_data=None,
            verification_status="skipped",
            mismatches=[],
            executed_at=None,
            approval=approval_dict_from_receipt(receipt),
        )
        assert "approval" not in raw


@pytest.mark.asyncio
async def test_unsigned_payload_includes_approval_when_resolved(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="a",
            action_type="t",
            target="https://x",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = GovernanceReceipt(
            intent_id=intent.id,
            verdict_id=verdict.id,
            project_id=pid,
            status="pending",
            verification="pending",
            mismatches=[],
            approval_status="approved",
            approved_at=datetime.now(UTC),
            approval_reason="ok",
        )
        session.add(receipt)
        await session.flush()
        raw = unsigned_receipt_for_sealing(
            receipt_id=str(receipt.id),
            intent=intent,
            verdict=verdict,
            execution_data=None,
            verification_status="skipped",
            mismatches=[],
            executed_at=None,
            approval=approval_dict_from_receipt(receipt),
        )
        assert raw.get("approval", {}).get("status") == "approved"


@pytest.mark.asyncio
async def test_verdict_row_snapshot_embedded_in_unsigned_payload(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="snap",
            action_type="tool.http.get",
            target="https://snap.example",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        raw = unsigned_receipt_for_sealing(
            receipt_id=str(uuid4()),
            intent=intent,
            verdict=verdict,
            execution_data=None,
            verification_status="pass",
            mismatches=[],
            executed_at=None,
            approval=None,
        )
        assert raw["verdict"]["verdict"] == verdict.verdict
        assert raw["verdict"]["id"] == str(verdict.id)


@pytest.mark.asyncio
async def test_sealed_receipt_with_hold_resolution_includes_approval_in_signed_payload(
    client: AsyncClient,
) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="a",
            action_type="t",
            target="https://hold",
            risk="high",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        verdict.verdict = "allow"
        receipt.approval_status = "approved"
        receipt.approved_at = datetime.now(UTC)
        vres = verify_execution(intent, {})
        sealed = await seal_receipt(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data={},
            executed_at=None,
            verification_result=vres,
        )
        keys = get_signing_keys()
        payload = unsigned_receipt_for_sealing(
            receipt_id=str(sealed.id),
            intent=intent,
            verdict=verdict,
            execution_data={},
            verification_status=vres.status,
            mismatches=list(vres.mismatches),
            executed_at=None,
            approval=approval_dict_from_receipt(sealed),
        )
        assert "approval" in payload
        msg = canonicalize(payload)
        assert ed25519.verify(keys.ed25519_public, msg, sealed.ed25519_sig)
