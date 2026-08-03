"""Pending hold expiration: auto-deny and re-seal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services.governance.approval_expire import expire_due_hold_receipts
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
from axiom.services.governance.receipt import create_pending_receipt, reset_governance_merkle_for_tests
from axiom.services.governance.verdict import render_verdict
from axiom.services.governance.verification import verify_sealed_governance_receipt_from_db
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_expire_due_hold_receipts_denies_and_seals_expired_pending(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        "/v1/governance/govern",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://x",
            "risk": "high",
        },
    )
    rid = UUID(g.json()["receipt_id"])
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, rid)
        assert rec is not None
        rec.approval_expires_at = datetime.now(UTC) - timedelta(minutes=1)

    async with session_scope() as session:
        n = len(await expire_due_hold_receipts(session))
        assert n == 1

    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, rid)
        assert rec is not None
        assert rec.approval_status == "expired"
        assert rec.status == "sealed"


@pytest.mark.asyncio
async def test_expire_skips_non_expired_pending_holds(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        "/v1/governance/govern",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://future",
            "risk": "high",
        },
    )
    rid = UUID(g.json()["receipt_id"])
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, rid)
        assert rec is not None
        rec.approval_expires_at = datetime.now(UTC) + timedelta(hours=2)

    async with session_scope() as session:
        n = len(await expire_due_hold_receipts(session))
        assert n == 0

    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, rid)
        assert rec is not None
        assert rec.approval_status == "pending"
        assert rec.status == "pending"


@pytest.mark.asyncio
async def test_expire_skips_already_resolved_holds(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        "/v1/governance/govern",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://resolved",
            "risk": "high",
        },
    )
    rid = UUID(g.json()["receipt_id"])
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, rid)
        assert rec is not None
        rec.approval_status = "approved"
        rec.approval_expires_at = datetime.now(UTC) - timedelta(minutes=10)

    async with session_scope() as session:
        n = len(await expire_due_hold_receipts(session))
        assert n == 0


@pytest.mark.asyncio
async def test_expire_handles_empty_pending_set(client: AsyncClient) -> None:
    _ = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        n = len(await expire_due_hold_receipts(session))
        assert n == 0


@pytest.mark.asyncio
async def test_expired_receipt_seals_with_expired_approval_and_verifies(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="exp",
            action_type="t",
            target="https://expire-proof",
            risk="high",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        receipt.approval_status = "pending"
        receipt.approval_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        rid = receipt.id

    async with session_scope() as session:
        n = len(await expire_due_hold_receipts(session))
        assert n == 1

    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, rid)
        v = await session.get(GovernanceVerdict, rec.verdict_id) if rec else None
        intent2 = await session.get(GovernanceIntent, rec.intent_id) if rec else None
        assert rec is not None and v is not None and intent2 is not None
        assert rec.approval_status == "expired"
        vr = verify_sealed_governance_receipt_from_db(rec, intent2, v)
        assert vr.valid is True
