"""Chain service: stats, close signatures, hold-resolution counter adjustments."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from axiom.db import session_scope
from axiom.models.governance import GovernanceChain
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services import auth as auth_service
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.governance.chain import (
    adjust_chain_after_hold_resolution,
    close_chain,
    create_chain,
    update_chain_stats,
    verify_chain_signatures,
)
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
from axiom.services.governance.receipt import (
    create_pending_receipt,
    reset_governance_merkle_for_tests,
    seal_receipt,
)
from axiom.services.governance.verdict import render_verdict
from axiom.services.governance.verification import verify_execution
from axiom.services.receipt.keys import get_signing_keys
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


G_PREFIX = "/v1/governance"
C_PREFIX = "/v1/chains"


async def _ensure_project() -> tuple[UUID, UUID]:
    """Return (project_id, user_id) with a minimal project row."""
    email = f"chain-svc-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(
            session,
            email=email,
            password="password1a",
            full_name="T",
        )
        project = await session.scalar(select(Project).where(Project.owner_user_id == user.id))
        if project is None:
            slug = f"chain-svc-{uuid4().hex[:8]}"
            project = Project(
                slug=slug,
                name="Test",
                description=None,
                owner_user_id=user.id,
            )
            session.add(project)
            await session.flush()
            session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    role=MemberRole.OWNER.value,
                    invited_by_user_id=None,
                )
            )
            await session.flush()
        pid = project.id
        uid = user.id
    return pid, uid


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_chain_creation_links_receipts_to_workflow_via_intent(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        p = await session.get(Project, UUID(fx["project_id"]))
        assert p is not None
        s = dict(p.settings or {})
        s["governance_policy"] = "starter-safe"
        p.settings = s

    r = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "chain-svc",
            "action_type": "tool.http.get",
            "target": "https://linked.example",
            "risk": "low",
            "workflow": "wf-chain-svc",
        },
    )
    assert r.status_code == 200, r.text
    cid = r.json()["chain_id"]
    assert cid is not None
    async with session_scope() as session:
        ch = await session.get(GovernanceChain, UUID(cid))
        assert ch is not None
        assert ch.status == "active"


@pytest.mark.asyncio
async def test_close_chain_ed25519_and_ml_dsa_verify() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        proj = await session.get(Project, pid)
        assert proj is not None
        s = dict(proj.settings or {})
        s["governance_policy"] = "starter-safe"
        proj.settings = s

        ch = await create_chain(session, pid, "seal-agent", "w")
        await session.flush()
        body = GovernRequest(
            agent_id="seal-agent",
            action_type="tool.http.get",
            target="https://z.example/x",
            risk="low",
        )
        intent = await declare_intent(session, pid, body, chain_id=ch.id)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        out = {
            "target": intent.target,
            "action_type": intent.action_type,
            "risk": intent.risk_declared,
        }
        vres = verify_execution(intent, out)
        await seal_receipt(
            session,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=out,
            executed_at=datetime.now(UTC),
            verification_result=vres,
        )
        await close_chain(session, ch)
        await session.commit()

    keys = get_signing_keys()
    async with session_scope() as session:
        ch2 = await session.get(GovernanceChain, ch.id)
        assert ch2 is not None
        assert ch2.chain_hash and ch2.ed25519_sig and ch2.ml_dsa_sig
        assert ed25519.verify(keys.ed25519_public, ch2.chain_hash, ch2.ed25519_sig)
        assert ml_dsa.verify(keys.ml_dsa_public, ch2.chain_hash, ch2.ml_dsa_sig)
        sigmap = verify_chain_signatures(ch2)
        assert sigmap is not None
        assert sigmap["ed25519"] is True and sigmap["ml_dsa_65"] is True


@pytest.mark.asyncio
async def test_close_chain_second_attempt_returns_conflict_at_api(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        p = await session.get(Project, UUID(fx["project_id"]))
        assert p is not None
        s = dict(p.settings or {})
        s["governance_policy"] = "starter-safe"
        p.settings = s

    g = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "close-twice",
            "action_type": "tool.http.get",
            "target": "https://c2",
            "risk": "low",
            "workflow": "close-twice-wf",
        },
    )
    cid = g.json()["chain_id"]
    cl = await client.post(
        f"{C_PREFIX}/{cid}/close",
        headers=_auth(fx["api_key_full"]),
        json={},
    )
    assert cl.status_code == 200
    bad = await client.post(
        f"{C_PREFIX}/{cid}/close",
        headers=_auth(fx["api_key_full"]),
        json={},
    )
    assert bad.status_code == 409


@pytest.mark.asyncio
async def test_chain_statistics_authorized_denied_held_accurate() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        ch = await create_chain(session, pid, "stats", None)
        await session.flush()
        await update_chain_stats(session, ch, "allow", None)
        await update_chain_stats(session, ch, "deny", None)
        await update_chain_stats(session, ch, "hold", None)
        assert ch.authorized == 1 and ch.denied == 1 and ch.held == 1
        assert ch.total_actions == 3
        await session.commit()


@pytest.mark.asyncio
async def test_adjust_chain_after_hold_resolution_updates_counters() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        ch = await create_chain(session, pid, "adj", None)
        await session.flush()
        await update_chain_stats(session, ch, "hold", None)
        assert ch.held == 1
        await adjust_chain_after_hold_resolution(session, ch.id, final_verdict="allow")
        assert ch.held == 0 and ch.authorized == 1
        await session.commit()

    async with session_scope() as session:
        ch2 = await create_chain(session, pid, "adj2", None)
        await session.flush()
        await update_chain_stats(session, ch2, "hold", None)
        await adjust_chain_after_hold_resolution(session, ch2.id, final_verdict="deny")
        assert ch2.held == 0 and ch2.denied == 1
        await session.commit()
