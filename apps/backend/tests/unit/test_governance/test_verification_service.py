"""Cryptographic verification: execution checks and independent receipt verify."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceIntent
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest, VerifyReceiptRequest
from axiom.services.crypto.canonical_json import canonicalize
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
from axiom.services.governance.verification import (
    verify_execution,
    verify_receipt_independent,
    verify_sealed_governance_receipt_from_db,
)
from axiom.services.receipt.keys import get_signing_keys
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


def test_verify_execution_detects_target_mismatch() -> None:
    intent = GovernanceIntent(
        project_id=uuid4(),
        agent_id="a",
        action_type="tool.x",
        target="https://expected",
        parameters={},
        risk_declared="low",
        mode="enforce",
        extra_metadata={},
    )
    res = verify_execution(intent, {"target": "https://other", "action_type": "tool.x"})
    assert res.status == "fail"
    assert any(m["field"] == "target" for m in res.mismatches)


def test_verify_execution_passes_when_aligned() -> None:
    intent = GovernanceIntent(
        project_id=uuid4(),
        agent_id="a",
        action_type="tool.x",
        target="https://ok",
        parameters={},
        risk_declared="low",
        mode="enforce",
        extra_metadata={},
    )
    res = verify_execution(
        intent,
        {"target": "https://ok", "action_type": "tool.x", "risk": "low"},
    )
    assert res.passed and res.status == "pass"


@pytest.mark.asyncio
async def test_verify_sealed_receipt_all_checks_green(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="v",
            action_type="tool.http.get",
            target="https://verify.example",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        out = {"target": intent.target, "action_type": intent.action_type, "risk": intent.risk_declared}
        vres = verify_execution(intent, out)
        sealed = await seal_receipt(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=out,
            executed_at=datetime.now(UTC),
            verification_result=vres,
        )
        vr = verify_sealed_governance_receipt_from_db(sealed, intent, verdict)
        assert vr.valid is True
        assert vr.checks["ed25519"] is True
        assert vr.checks["ml_dsa_65"] is True
        assert vr.checks["merkle"] is True


@pytest.mark.asyncio
async def test_verify_independent_tampered_body_fails_ed25519(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="v",
            action_type="tool.http.get",
            target="https://tamper.example",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        out = {"target": intent.target, "action_type": intent.action_type, "risk": intent.risk_declared}
        vres = verify_execution(intent, out)
        sealed = await seal_receipt(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=out,
            executed_at=datetime.now(UTC),
            verification_result=vres,
        )
        keys = get_signing_keys()
        good_obj = unsigned_receipt_for_sealing(
            receipt_id=str(sealed.id),
            intent=intent,
            verdict=verdict,
            execution_data=out,
            verification_status=vres.status,
            mismatches=list(vres.mismatches),
            executed_at=sealed.executed_at,
            approval=approval_dict_from_receipt(sealed),
        )
        bad_obj = dict(good_obj)
        bad_obj["v"] = 99
        body_req = VerifyReceiptRequest(
            receipt_json=json.dumps(bad_obj),
            ed25519_signature=base64.b64encode(sealed.ed25519_sig).decode("ascii"),
            ml_dsa_signature=base64.b64encode(sealed.ml_dsa_sig).decode("ascii"),
            merkle_proof=list(sealed.merkle_proof.get("path", [])) if sealed.merkle_proof else [],
            merkle_root=sealed.merkle_root.hex() if sealed.merkle_root else "",
            ed25519_public_key=keys.ed25519_public,
            ml_dsa_public_key=base64.b64encode(keys.ml_dsa_public).decode("ascii"),
            leaf_index=sealed.merkle_proof.get("leaf_index") if sealed.merkle_proof else None,
            tree_size=sealed.merkle_proof.get("tree_size") if sealed.merkle_proof else None,
        )
        vr = verify_receipt_independent(body_req)
        assert vr.valid is False
        assert vr.checks["ed25519"] is False


@pytest.mark.asyncio
async def test_verify_independent_bad_signature_bytes_fail(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="v",
            action_type="tool.http.get",
            target="https://sig.example",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        out = {"target": intent.target, "action_type": intent.action_type, "risk": intent.risk_declared}
        vres = verify_execution(intent, out)
        sealed = await seal_receipt(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=out,
            executed_at=datetime.now(UTC),
            verification_result=vres,
        )
        keys = get_signing_keys()
        good_json = canonicalize(
            unsigned_receipt_for_sealing(
                receipt_id=str(sealed.id),
                intent=intent,
                verdict=verdict,
                execution_data=out,
                verification_status=vres.status,
                mismatches=list(vres.mismatches),
                executed_at=sealed.executed_at,
                approval=approval_dict_from_receipt(sealed),
            )
        ).decode("utf-8")
        bad_sig = bytearray(sealed.ed25519_sig)
        bad_sig[0] ^= 0xFF
        body_req = VerifyReceiptRequest(
            receipt_json=good_json,
            ed25519_signature=base64.b64encode(bytes(bad_sig)).decode("ascii"),
            ml_dsa_signature=base64.b64encode(sealed.ml_dsa_sig).decode("ascii"),
            merkle_proof=list(sealed.merkle_proof.get("path", [])) if sealed.merkle_proof else [],
            merkle_root=sealed.merkle_root.hex() if sealed.merkle_root else "",
            ed25519_public_key=keys.ed25519_public,
            ml_dsa_public_key=base64.b64encode(keys.ml_dsa_public).decode("ascii"),
            leaf_index=sealed.merkle_proof.get("leaf_index") if sealed.merkle_proof else None,
            tree_size=sealed.merkle_proof.get("tree_size") if sealed.merkle_proof else None,
        )
        vr = verify_receipt_independent(body_req)
        assert vr.valid is False
        assert vr.checks["ed25519"] is False


def test_verify_independent_invalid_ed25519_base64_errors() -> None:
    vr = verify_receipt_independent(
        VerifyReceiptRequest(
            receipt_json="{}",
            ed25519_signature="not-valid-base64!!!",
            merkle_root="00" * 32,
            ed25519_public_key=get_signing_keys().ed25519_public,
        )
    )
    assert vr.valid is False
    assert any("ed25519_signature" in e for e in vr.errors)


@pytest.mark.asyncio
async def test_verify_independent_includes_per_check_breakdown(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="v",
            action_type="tool.http.get",
            target="https://breakdown.example",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        out = {"target": intent.target, "action_type": intent.action_type, "risk": intent.risk_declared}
        vres = verify_execution(intent, out)
        sealed = await seal_receipt(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=out,
            executed_at=datetime.now(UTC),
            verification_result=vres,
        )
        vr = verify_sealed_governance_receipt_from_db(sealed, intent, verdict)
        assert set(vr.checks.keys()) == {"ed25519", "ml_dsa_65", "merkle"}
