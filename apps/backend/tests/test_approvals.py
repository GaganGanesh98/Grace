"""Human approval workflow for held governance receipts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceReceipt
from axiom.models.project import Project
from axiom.services.governance.approval_expire import expire_due_hold_receipts
from tests.conftest import auth_headers, login_user, signup_user, unique_email
from tests.fixtures.governance import bootstrap_project_with_api_key


def _api_auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


G = "/v1/governance"


@pytest.mark.asyncio
async def test_govern_hold_sets_approval_pending(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    r = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "hold-agent",
            "action_type": "tool.exec",
            "target": "https://x",
            "risk": "high",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "hold"
    assert body["approval_status"] == "pending"
    assert body["approval_expires_at"] is not None
    rid = UUID(body["receipt_id"])
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, rid)
        assert rec is not None
        assert rec.approval_status == "pending"
        assert rec.approval_expires_at is not None


@pytest.mark.asyncio
async def test_approve_receipt(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://x",
            "risk": "high",
        },
    )
    assert g.status_code == 200, g.text
    rid = g.json()["receipt_id"]

    h = auth_headers(fx["user_access"])
    ap = await client.post(
        f"{G}/receipts/{rid}/approve",
        headers=h,
        json={},
    )
    assert ap.status_code == 200, ap.text
    out = ap.json()
    assert out["approval_status"] == "approved"
    assert out["verdict"] == "allow"

    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, UUID(rid))
        assert rec is not None
        assert rec.approval_status == "approved"
        assert rec.status == "sealed"


@pytest.mark.asyncio
async def test_reject_receipt(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://x",
            "risk": "high",
        },
    )
    rid = g.json()["receipt_id"]
    h = auth_headers(fx["user_access"])
    rj = await client.post(
        f"{G}/receipts/{rid}/reject",
        headers=h,
        json={"reason": "no"},
    )
    assert rj.status_code == 200, rj.text
    assert rj.json()["approval_status"] == "rejected"
    assert rj.json()["verdict"] == "deny"


@pytest.mark.asyncio
async def test_approve_already_approved_returns_conflict(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://x",
            "risk": "high",
        },
    )
    rid = g.json()["receipt_id"]
    h = auth_headers(fx["user_access"])
    assert (await client.post(f"{G}/receipts/{rid}/approve", headers=h, json={})).status_code == 200
    r2 = await client.post(f"{G}/receipts/{rid}/approve", headers=h, json={})
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_approve_expired_returns_gone(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://x",
            "risk": "high",
        },
    )
    rid = g.json()["receipt_id"]
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, UUID(rid))
        assert rec is not None
        rec.approval_expires_at = datetime.now(UTC) - timedelta(minutes=5)

    h = auth_headers(fx["user_access"])
    r = await client.post(f"{G}/receipts/{rid}/approve", headers=h, json={})
    assert r.status_code == 410


@pytest.mark.asyncio
async def test_approve_other_project_forbidden(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://x",
            "risk": "high",
        },
    )
    rid = g.json()["receipt_id"]

    other_email = unique_email()
    await signup_user(client, other_email, "password1a")
    other = await login_user(client, other_email, "password1a")
    h2 = auth_headers(other["access_token"])

    r = await client.post(f"{G}/receipts/{rid}/approve", headers=h2, json={})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_pending_receipts_endpoint(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = fx["project_id"]
    async with session_scope() as session:
        project = await session.get(Project, UUID(pid))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    for _ in range(3):
        gr = await client.post(
            f"{G}/govern",
            headers=_api_auth(fx["api_key_full"]),
            json={
                "agent_id": "a1",
                "action_type": "t",
                "target": "https://x",
                "risk": "high",
            },
        )
        assert gr.status_code == 200
    al = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://low",
            "risk": "low",
        },
    )
    assert al.status_code == 200

    h = auth_headers(fx["user_access"])
    pr = await client.get(
        f"{G}/receipts/pending",
        headers=h,
        params={"project_id": pid},
    )
    assert pr.status_code == 200, pr.text
    data = pr.json()
    assert data["total"] == 3
    assert len(data["receipts"]) == 3


@pytest.mark.asyncio
async def test_auto_expire_background_task(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        s = dict(project.settings)
        s["governance_policy"] = "starter-safe"
        project.settings = s

    g = await client.post(
        f"{G}/govern",
        headers=_api_auth(fx["api_key_full"]),
        json={
            "agent_id": "a1",
            "action_type": "t",
            "target": "https://x",
            "risk": "high",
        },
    )
    rid = g.json()["receipt_id"]
    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, UUID(rid))
        assert rec is not None
        rec.approval_expires_at = datetime.now(UTC) - timedelta(minutes=1)

    async with session_scope() as session:
        n = len(await expire_due_hold_receipts(session))
        assert n == 1

    async with session_scope() as session:
        rec = await session.get(GovernanceReceipt, UUID(rid))
        assert rec is not None
        assert rec.approval_status == "expired"
        assert rec.status == "sealed"
