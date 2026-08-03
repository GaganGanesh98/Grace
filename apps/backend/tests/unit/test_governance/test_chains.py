"""Governance workflow chains — lifecycle, stats, sealing, API, auto-close."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from axiom.db import session_scope
from axiom.models.governance import GovernanceChain
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services import auth as auth_service
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.governance.chain import (
    ChainValidationError,
    auto_close_stale_chains,
    close_chain,
    compute_chain_hash,
    create_chain,
    get_or_create_chain,
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


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


async def _ensure_project() -> tuple[UUID, UUID]:
    """Return (project_id, user_id) with a minimal project row."""
    email = f"chain-unit-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(
            session,
            email=email,
            password="password1a",
            full_name="T",
        )
        project = await session.scalar(select(Project).where(Project.owner_user_id == user.id))
        if project is None:
            slug = f"chain-{uuid4().hex[:8]}"
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


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


G_PREFIX = "/v1/governance"
C_PREFIX = "/v1/chains"


@pytest.mark.asyncio
async def test_create_chain_active() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        ch = await create_chain(session, pid, "agent-a", "My workflow")
        await session.commit()
        assert ch.status == "active"
        assert ch.workflow_name == "My workflow"
        assert ch.agent_id == "agent-a"


@pytest.mark.asyncio
async def test_get_or_create_workflow_creates() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        ch = await get_or_create_chain(session, pid, "ag", "wf", None)
        assert ch is not None
        assert ch.workflow_name == "wf"
        await session.commit()


@pytest.mark.asyncio
async def test_get_or_create_chain_id_returns_existing() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        created = await create_chain(session, pid, "ag", "w")
        await session.flush()
        cid = str(created.id)
        again = await get_or_create_chain(session, pid, "ag", None, cid)
        assert again is not None
        assert again.id == created.id
        await session.commit()


@pytest.mark.asyncio
async def test_get_or_create_wrong_agent() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        created = await create_chain(session, pid, "agent-a", "w")
        await session.flush()
        with pytest.raises(ChainValidationError, match="different agent"):
            await get_or_create_chain(session, pid, "other", None, str(created.id))


@pytest.mark.asyncio
async def test_get_or_create_invalid_chain_id() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        with pytest.raises(ChainValidationError):
            await get_or_create_chain(session, pid, "ag", None, str(uuid4()))


@pytest.mark.asyncio
async def test_get_or_create_bad_uuid() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        with pytest.raises(ChainValidationError, match="UUID"):
            await get_or_create_chain(session, pid, "ag", None, "not-a-uuid")


@pytest.mark.asyncio
async def test_get_or_create_standalone_none() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        ch = await get_or_create_chain(session, pid, "ag", None, None)
        assert ch is None
        await session.commit()


@pytest.mark.asyncio
async def test_stats_allow_deny_hold_and_compliance() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        ch = await create_chain(session, pid, "a", None)
        await session.flush()
        await update_chain_stats(session, ch, "allow", None)
        assert ch.total_actions == 1 and ch.authorized == 1
        await update_chain_stats(session, ch, "deny", None)
        assert ch.total_actions == 2 and ch.denied == 1
        await update_chain_stats(session, ch, "hold", None)
        assert ch.total_actions == 3 and ch.held == 1
        await update_chain_stats(session, ch, None, "pass")
        assert ch.compliant == 1
        await update_chain_stats(session, ch, None, "fail")
        assert ch.non_compliant == 1
        await session.commit()


@pytest.mark.asyncio
async def test_close_chain_dual_signatures_and_hash() -> None:
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
        assert ch2.chain_hash is not None and ch2.ed25519_sig and ch2.ml_dsa_sig
        assert ed25519.verify(keys.ed25519_public, ch2.chain_hash, ch2.ed25519_sig)
        assert ml_dsa.verify(keys.ml_dsa_public, ch2.chain_hash, ch2.ml_dsa_sig)
        sigmap = verify_chain_signatures(ch2)
        assert sigmap is not None
        assert sigmap["ed25519"] is True and sigmap["ml_dsa_65"] is True


@pytest.mark.asyncio
async def test_chain_hash_deterministic_and_order_sensitive() -> None:
    a = b"\x00" * 32
    b = b"\x01" * 32
    h1 = compute_chain_hash([a, b])
    h2 = compute_chain_hash([a, b])
    assert h1 == h2
    assert compute_chain_hash([b, a]) != h1


@pytest.mark.asyncio
async def test_chain_hash_tamper_changes_digest() -> None:
    a = b"\xab" * 32
    b = b"\xcd" * 32
    h = compute_chain_hash([a, b])
    a2 = bytes(32)
    assert compute_chain_hash([a2, b]) != h


@pytest.mark.asyncio
async def test_api_govern_workflow_creates_chain(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        p = await session.get(Project, UUID(fx["project_id"]))
        assert p is not None
        s = dict(p.settings)
        s["governance_policy"] = "starter-safe"
        p.settings = s

    r = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "wf-agent",
            "action_type": "tool.http.get",
            "target": "https://api.example/w",
            "risk": "low",
            "workflow": "Tesla research",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("chain_id") is not None


@pytest.mark.asyncio
async def test_api_govern_chain_id_second_call_updates_stats(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        p = await session.get(Project, UUID(fx["project_id"]))
        assert p is not None
        s = dict(p.settings)
        s["governance_policy"] = "starter-safe"
        p.settings = s

    g1 = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "same",
            "action_type": "tool.http.get",
            "target": "https://a",
            "risk": "low",
            "workflow": "w",
        },
    )
    cid = g1.json()["chain_id"]
    g2 = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "same",
            "action_type": "tool.http.get",
            "target": "https://b",
            "risk": "low",
            "chain_id": cid,
        },
    )
    assert g2.status_code == 200
    assert g2.json()["chain_id"] == cid

    r = await client.get(f"{C_PREFIX}/{cid}", headers=_auth(fx["api_key_full"]))
    assert r.status_code == 200
    assert r.json()["total_actions"] == 2


@pytest.mark.asyncio
async def test_api_govern_invalid_chain_id_400(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "x",
            "action_type": "t",
            "target": "https://x",
            "risk": "low",
            "chain_id": str(uuid4()),
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_api_close_and_get_chain(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        p = await session.get(Project, UUID(fx["project_id"]))
        assert p is not None
        s = dict(p.settings)
        s["governance_policy"] = "starter-safe"
        p.settings = s

    g = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "close-test",
            "action_type": "tool.http.get",
            "target": "https://c",
            "risk": "low",
            "workflow": "close-me",
        },
    )
    cid = g.json()["chain_id"]
    cl = await client.post(
        f"{C_PREFIX}/{cid}/close",
        headers=_auth(fx["api_key_full"]),
        json={},
    )
    assert cl.status_code == 200, cl.text
    assert cl.json()["status"] == "sealed"
    assert cl.json()["chain_signature"] is not None

    bad = await client.post(
        f"{C_PREFIX}/{cid}/close",
        headers=_auth(fx["api_key_full"]),
        json={},
    )
    assert bad.status_code == 409

    lst = await client.get(
        f"{C_PREFIX}",
        headers=_auth(fx["api_key_full"]),
        params={"page": 1, "per_page": 10},
    )
    assert lst.status_code == 200
    assert lst.json()["total"] >= 1


@pytest.mark.asyncio
async def test_backward_compat_govern_no_chain_fields(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        p = await session.get(Project, UUID(fx["project_id"]))
        assert p is not None
        s = dict(p.settings)
        s["governance_policy"] = "starter-safe"
        p.settings = s

    r = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "legacy",
            "action_type": "tool.http.get",
            "target": "https://legacy",
            "risk": "low",
        },
    )
    assert r.status_code == 200
    assert r.json().get("chain_id") is None


@pytest.mark.asyncio
async def test_auto_close_stale_and_not_recent() -> None:
    pid, _ = await _ensure_project()
    async with session_scope() as session:
        ch_old = await create_chain(session, pid, "auto", "stale")
        ch_new = await create_chain(session, pid, "auto", "fresh")
        old_t = datetime.now(UTC) - timedelta(hours=2)
        await session.execute(
            update(GovernanceChain)
            .where(GovernanceChain.id == ch_old.id)
            .values(last_activity=old_t)
        )
        n = await auto_close_stale_chains(session, pid, timeout_minutes=30)
        await session.commit()
        assert n >= 1

    async with session_scope() as session:
        o = await session.get(GovernanceChain, ch_old.id)
        n2 = await session.get(GovernanceChain, ch_new.id)
        assert o is not None and o.status == "auto_closed"
        assert n2 is not None and n2.status == "active"


@pytest.mark.asyncio
async def test_report_updates_chain_compliance(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    async with session_scope() as session:
        p = await session.get(Project, UUID(fx["project_id"]))
        assert p is not None
        s = dict(p.settings)
        s["governance_policy"] = "starter-safe"
        p.settings = s

    g = await client.post(
        f"{G_PREFIX}/govern",
        headers=_auth(fx["api_key_full"]),
        json={
            "agent_id": "rep",
            "action_type": "tool.http.get",
            "target": "https://rep-target",
            "risk": "low",
            "workflow": "w2",
        },
    )
    rid = g.json()["receipt_id"]
    cid = g.json()["chain_id"]
    rep = await client.post(
        f"{G_PREFIX}/report",
        headers=_auth(fx["api_key_full"]),
        json={
            "receipt_id": rid,
            "outcome": {
                "target": "https://rep-target",
                "action_type": "tool.http.get",
                "risk": "low",
            },
        },
    )
    assert rep.status_code == 200
    gr = await client.get(f"{C_PREFIX}/{cid}", headers=_auth(fx["api_key_full"]))
    assert gr.status_code == 200
    body = gr.json()
    assert body["compliant"] >= 1
