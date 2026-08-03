"""Receipt sealing and cryptography."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
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
async def test_seal_pipeline_signatures_and_merkle(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])

    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

        body = GovernRequest(
            agent_id="seal-agent",
            action_type="tool.http.get",
            target="https://api.example.com/z",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        context = await enrich_context(session, intent)
        pr = evaluate_policy(intent, context)
        verdict = await render_verdict(session, intent, pr, context)
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
        assert sealed.status == "sealed"
        assert sealed.ed25519_sig and sealed.ml_dsa_sig and sealed.receipt_hash
        assert sealed.merkle_root is not None

        keys = get_signing_keys()
        payload = unsigned_receipt_for_sealing(
            receipt_id=str(sealed.id),
            intent=intent,
            verdict=verdict,
            execution_data=outcome,
            verification_status=vres.status,
            mismatches=list(vres.mismatches),
            executed_at=sealed.executed_at,
            approval=approval_dict_from_receipt(sealed),
        )
        msg = canonicalize(payload)
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
async def test_tampered_payload_breaks_signature(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])

    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

        body = GovernRequest(
            agent_id="a2",
            action_type="t",
            target="https://x",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        context = await enrich_context(session, intent)
        pr = evaluate_policy(intent, context)
        verdict = await render_verdict(session, intent, pr, context)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        outcome = {"target": intent.target, "action_type": intent.action_type}
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
        bad = bytearray(sealed.ed25519_sig)
        bad[0] ^= 0xFF
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
        assert not ed25519.verify(keys.ed25519_public, msg, bytes(bad))
