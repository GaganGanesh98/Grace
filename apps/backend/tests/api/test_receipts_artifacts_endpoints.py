"""Phase 7.2 — /v1/receipts and artifact download."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.agent_run import AgentRun
from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


async def _headers_and_project(client: AsyncClient) -> tuple[dict[str, str], str]:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "CC", "slug": unique_slug("cc-proj")},
    )
    assert project.status_code == 201, project.text
    return h, project.json()["data"]["id"]


@pytest.mark.asyncio
async def test_run_detail_includes_receipt_ids_and_artifacts(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "a" * 40, "name": "oai"},
    )
    assert vk.status_code == 201, vk.text
    vault_key_id = vk.json()["id"]
    ad = await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "bot",
            "model": "gpt-4o",
            "vault_key_id": vault_key_id,
            "system_prompt": "test",
            "tools_config": {},
        },
    )
    assert ad.status_code == 201, ad.text
    def_id = ad.json()["data"]["id"]

    create = await client.post(
        f"/v1/agent-runs?project_id={pid}",
        headers=h,
        json={"agent_definition_id": def_id, "input": {}},
    )
    assert create.status_code == 201, create.text
    run_id = create.json()["data"]["id"]

    async with session_scope() as db:
        row = await db.get(AgentRun, UUID(run_id))
        assert row is not None
        row.receipt_ids = ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]
        row.artifacts = [
            {
                "tool": "file_write",
                "path": "x.txt",
                "url": f"/api/projects/{pid}/agent-runs/{run_id}/artifacts/x.txt",
                "content_type": "text/plain",
                "size_bytes": 2,
                "created_at": "2026-04-21T00:00:00+00:00",
            }
        ]
        await db.commit()

    r = await client.get(f"/v1/agent-runs/{run_id}?project_id={pid}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["receipt_ids"] == ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["tool"] == "file_write"


@pytest.mark.asyncio
async def test_receipt_detail_returns_full_signature_and_merkle(client: AsyncClient) -> None:
    """Sealed receipt from governance tests — GET /v1/receipts returns structured payload."""
    from datetime import UTC, datetime

    from axiom.schemas.governance import GovernRequest
    from axiom.services.governance.context import enrich_context
    from axiom.services.governance.intent import declare_intent
    from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
    from axiom.services.governance.receipt import create_pending_receipt, reset_governance_merkle_for_tests, seal_receipt
    from axiom.services.governance.verdict import render_verdict
    from axiom.services.governance.verification import verify_execution

    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    try:
        h, pid = await _headers_and_project(client)
        async with session_scope() as session:
            from axiom.models.project import Project

            project = await session.get(Project, UUID(pid))
            assert project is not None
            s = dict(project.settings)
            s["governance_policy"] = "starter-safe"
            project.settings = s

            body = GovernRequest(
                agent_id="cc-agent",
                action_type="tool.llm.groq",
                target="https://api.example.com/v1",
                risk="low",
            )
            intent = await declare_intent(session, UUID(pid), body)
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
            await seal_receipt(
                session,
                receipt=receipt,
                intent=intent,
                verdict=verdict,
                execution_data=outcome,
                executed_at=datetime.now(UTC),
                verification_result=vres,
            )
            await session.commit()
            rid = str(receipt.id)

        r = await client.get(f"/v1/receipts/{rid}?project_id={pid}", headers=h)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["receipt_id"] == rid
        assert "signatures" in payload
        assert "merkle" in payload
        assert payload["merkle"].get("depth") is not None
        assert len(payload.get("pipeline", [])) == 6
    finally:
        reset_governance_merkle_for_tests()
        clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_artifact_endpoint_streams_file_with_correct_mime(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h, pid = await _headers_and_project(client)
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "a" * 40, "name": "oai"},
    )
    assert vk.status_code == 201, vk.text
    vault_key_id = vk.json()["id"]
    ad = await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "bot2",
            "model": "gpt-4o",
            "vault_key_id": vault_key_id,
            "system_prompt": "test",
            "tools_config": {},
        },
    )
    assert ad.status_code == 201, ad.text
    def_id = ad.json()["data"]["id"]
    create = await client.post(
        f"/v1/agent-runs?project_id={pid}",
        headers=h,
        json={"agent_definition_id": def_id, "input": {}},
    )
    assert create.status_code == 201, create.text
    run_id = create.json()["data"]["id"]
    run_uuid = UUID(run_id)

    target = tmp_path / str(run_uuid)
    target.mkdir(parents=True)
    (target / "hello.txt").write_bytes(b"hello")

    import axiom.routers.v1.command_center as cc

    def fake_path(rid: UUID, name: str, *, root: Path | None = None) -> Path:
        return tmp_path / str(rid) / name

    monkeypatch.setattr(cc, "artifact_path_for_run", fake_path)

    r = await client.get(
        f"/v1/agent-runs/{run_id}/artifacts/hello.txt?project_id={pid}",
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.content == b"hello"
    assert "attachment" in r.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_cross_project_access_returns_403(client: AsyncClient) -> None:
    """Receipt or run scoped to another project → 403 when JWT targets a different workspace."""
    from datetime import UTC, datetime

    from axiom.schemas.governance import GovernRequest
    from axiom.services.governance.context import enrich_context
    from axiom.services.governance.intent import declare_intent
    from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
    from axiom.services.governance.receipt import create_pending_receipt, reset_governance_merkle_for_tests, seal_receipt
    from axiom.services.governance.verdict import render_verdict
    from axiom.services.governance.verification import verify_execution

    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    try:
        email = unique_email()
        tokens = await signup_user(client, email, "password1a")
        h = auth_headers(tokens["access_token"])
        p1 = await client.post(
            "/api/v1/projects",
            headers=h,
            json={"name": "P1", "slug": unique_slug("p1")},
        )
        assert p1.status_code == 201, p1.text
        id1 = p1.json()["data"]["id"]
        p2 = await client.post(
            "/api/v1/projects",
            headers=h,
            json={"name": "P2", "slug": unique_slug("p2")},
        )
        assert p2.status_code == 201, p2.text
        id2 = p2.json()["data"]["id"]

        async with session_scope() as session:
            from axiom.models.project import Project

            project = await session.get(Project, UUID(id1))
            assert project is not None
            s = dict(project.settings)
            s["governance_policy"] = "starter-safe"
            project.settings = s

            body = GovernRequest(
                agent_id="x-agent",
                action_type="tool.test",
                target="https://example.com",
                risk="low",
            )
            intent = await declare_intent(session, UUID(id1), body)
            context = await enrich_context(session, intent)
            pr = evaluate_policy(intent, context)
            verdict = await render_verdict(session, intent, pr, context)
            receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
            outcome = {"target": intent.target, "action_type": intent.action_type, "risk": intent.risk_declared}
            vres = verify_execution(intent, outcome)
            await seal_receipt(
                session,
                receipt=receipt,
                intent=intent,
                verdict=verdict,
                execution_data=outcome,
                executed_at=datetime.now(UTC),
                verification_result=vres,
            )
            await session.commit()
            rid = str(receipt.id)

        r = await client.get(f"/v1/receipts/{rid}?project_id={id2}", headers=h)
        assert r.status_code == 403, r.text
    finally:
        reset_governance_merkle_for_tests()
        clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_nonexistent_receipt_returns_404_with_diagnostic(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    missing = "00000000-0000-0000-0000-000000000099"
    r = await client.get(f"/v1/receipts/{missing}?project_id={pid}", headers=h)
    assert r.status_code == 404, r.text
    body = r.json()
    detail = body.get("detail", body)
    assert isinstance(detail, dict)
    assert detail.get("receipt_id") == missing
