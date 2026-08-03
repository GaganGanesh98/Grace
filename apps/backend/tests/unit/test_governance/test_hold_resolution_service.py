"""Sealing held receipts after human decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceChain, GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services.governance.chain import adjust_chain_after_hold_resolution, create_chain, update_chain_stats
from axiom.services.governance.context import enrich_context
from axiom.services.governance.hold_resolution import seal_pending_after_hold_decision
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
from axiom.services.governance.receipt import create_pending_receipt, reset_governance_merkle_for_tests
from axiom.services.governance.verdict import render_verdict
from axiom.services.governance.verification import verify_execution, verify_sealed_governance_receipt_from_db
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_seal_after_hold_approval_flips_verdict_to_allow_and_verifies(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        ch = await create_chain(session, pid, "hold-res", "w")
        await session.flush()
        body = GovernRequest(
            agent_id="hold-res",
            action_type="tool.exec",
            target="https://h",
            risk="high",
        )
        intent = await declare_intent(session, pid, body, chain_id=ch.id)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        await update_chain_stats(session, ch, "hold", None)
        verdict.verdict = "allow"
        receipt.approval_status = "approved"
        receipt.approved_at = datetime.now(UTC)
        vres = verify_execution(intent, {})
        sealed = await seal_pending_after_hold_decision(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
        )
        await adjust_chain_after_hold_resolution(session, intent.chain_id, final_verdict="allow")
        await session.commit()

    assert sealed.status == "sealed"
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, sealed.id)
        vrow = await session.get(GovernanceVerdict, sealed.verdict_id)
        intent2 = await session.get(GovernanceIntent, sealed.intent_id)
        assert rec is not None and vrow is not None and intent2 is not None
        vr = verify_sealed_governance_receipt_from_db(rec, intent2, vrow)
        assert vr.valid is True

    async with session_scope() as session:
        ch2 = await session.get(GovernanceChain, ch.id)
        assert ch2 is not None
        assert ch2.held == 0
        assert ch2.authorized == 1


@pytest.mark.asyncio
async def test_seal_after_hold_rejection_flips_verdict_to_deny_and_verifies(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        ch = await create_chain(session, pid, "hold-rej", "w")
        await session.flush()
        body = GovernRequest(
            agent_id="hold-rej",
            action_type="tool.exec",
            target="https://h",
            risk="high",
        )
        intent = await declare_intent(session, pid, body, chain_id=ch.id)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        await update_chain_stats(session, ch, "hold", None)
        verdict.verdict = "deny"
        verdict.reason = "rejected"
        receipt.approval_status = "rejected"
        vres = verify_execution(intent, {})
        sealed = await seal_pending_after_hold_decision(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
        )
        await adjust_chain_after_hold_resolution(session, intent.chain_id, final_verdict="deny")
        await session.commit()

    assert sealed.status == "sealed"
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, sealed.id)
        vrow = await session.get(GovernanceVerdict, sealed.verdict_id)
        intent2 = await session.get(GovernanceIntent, sealed.intent_id)
        assert rec is not None and vrow is not None and intent2 is not None
        vr = verify_sealed_governance_receipt_from_db(rec, intent2, vrow)
        assert vr.valid is True
