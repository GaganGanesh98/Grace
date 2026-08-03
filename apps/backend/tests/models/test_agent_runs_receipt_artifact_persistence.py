"""Phase 7.2 — agent_runs receipt_ids + artifacts persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import session_scope
from axiom.models.agent_run import AgentRun
from axiom.workers.agent_worker import process_run
from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_migration_adds_columns_if_missing() -> None:
    """artifacts column exists after Phase 7.2 migration."""
    async with session_scope() as db:
        res = await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agent_runs' "
                "AND column_name IN ('receipt_ids', 'artifacts')"
            )
        )
        names = {row[0] for row in res.fetchall()}
    assert "receipt_ids" in names
    assert "artifacts" in names


async def _project_with_definition(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "AR", "slug": unique_slug("ar-persist")},
    )
    assert project.status_code == 201, project.text
    pid = project.json()["data"]["id"]
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
    return h, pid, str(def_id)


@pytest.mark.asyncio
async def test_worker_writes_both_lists_on_success(client: AsyncClient) -> None:
    """Terminal success persists receipt_ids and artifacts from the ReAct outcome."""
    h, pid, def_id = await _project_with_definition(client)
    create = await client.post(
        f"/v1/agent-runs?project_id={pid}",
        headers=h,
        json={"agent_definition_id": def_id, "input": {}},
    )
    assert create.status_code == 201, create.text
    run_id = create.json()["data"]["id"]
    rid = str(run_id)

    outcome = {
        "ok": True,
        "final_text": "done",
        "iterations": 1,
        "total_tokens": 5,
        "receipt_ids": ["11111111-1111-1111-1111-111111111111"],
        "artifacts": [
            {
                "tool": "file_write",
                "path": "a.txt",
                "url": f"/api/projects/{pid}/agent-runs/{rid}/artifacts/a.txt",
                "content_type": "text/plain",
                "size_bytes": 1,
                "created_at": "2026-04-21T00:00:00+00:00",
            }
        ],
    }

    async def fake_react_loop(**_kwargs: object) -> dict:
        return outcome

    with (
        patch("axiom.workers.agent_worker.run_react_loop", side_effect=fake_react_loop),
        patch(
            "axiom.workers.agent_worker._resolve_project_gateway_key",
            new_callable=AsyncMock,
            return_value="axm_test_key",
        ),
        patch("axiom.workers.agent_worker.EventPublisher.publish", new_callable=AsyncMock),
        patch("axiom.workers.agent_worker.Heartbeat") as hb_cls,
    ):
        hb_cls.return_value.start = lambda: None
        hb_cls.return_value.stop = AsyncMock()
        await process_run(rid)

    async with session_scope() as db:
        row = await db.get(AgentRun, UUID(rid))
        assert row is not None
        assert row.status == "succeeded"
        assert row.total_tokens == 5
        assert row.receipt_ids == ["11111111-1111-1111-1111-111111111111"]
        assert len(row.artifacts) == 1
        assert row.artifacts[0]["tool"] == "file_write"


@pytest.mark.asyncio
async def test_worker_writes_empty_lists_on_llm_failure(client: AsyncClient) -> None:
    """Failed run stores [] for receipt_ids and artifacts, not NULL."""
    h, pid, def_id = await _project_with_definition(client)
    create = await client.post(
        f"/v1/agent-runs?project_id={pid}",
        headers=h,
        json={"agent_definition_id": def_id, "input": {}},
    )
    assert create.status_code == 201, create.text
    run_id = create.json()["data"]["id"]
    rid = str(run_id)

    outcome = {
        "ok": False,
        "error": "llm_step_failed",
        "detail": "boom",
        "receipt_ids": [],
        "artifacts": [],
    }

    async def fake_react_loop(**_kwargs: object) -> dict:
        return outcome

    with (
        patch("axiom.workers.agent_worker.run_react_loop", side_effect=fake_react_loop),
        patch(
            "axiom.workers.agent_worker._resolve_project_gateway_key",
            new_callable=AsyncMock,
            return_value="axm_test_key",
        ),
        patch("axiom.workers.agent_worker.EventPublisher.publish", new_callable=AsyncMock),
        patch("axiom.workers.agent_worker.Heartbeat") as hb_cls,
    ):
        hb_cls.return_value.start = lambda: None
        hb_cls.return_value.stop = AsyncMock()
        await process_run(rid)

    async with session_scope() as db:
        row = await db.get(AgentRun, UUID(rid))
        assert row is not None
        assert row.status == "failed"
        assert row.receipt_ids == []
        assert row.artifacts == []


@pytest.mark.asyncio
async def test_transaction_rolls_back_if_persistence_fails(client: AsyncClient) -> None:
    """Third DB commit (finalize) failure leaves no partial success; run ends failed."""
    h, pid, def_id = await _project_with_definition(client)
    create = await client.post(
        f"/v1/agent-runs?project_id={pid}",
        headers=h,
        json={"agent_definition_id": def_id, "input": {}},
    )
    assert create.status_code == 201, create.text
    run_id = create.json()["data"]["id"]
    rid = str(run_id)

    outcome = {
        "ok": True,
        "final_text": "x",
        "iterations": 1,
        "receipt_ids": ["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
        "artifacts": [],
    }

    async def fake_react_loop(**_kwargs: object) -> dict:
        return outcome

    orig = AsyncSession.commit
    calls = {"n": 0}

    async def flaky_commit(self) -> None:  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("commit denied")
        return await orig(self)

    with (
        patch("axiom.workers.agent_worker.run_react_loop", side_effect=fake_react_loop),
        patch(
            "axiom.workers.agent_worker._resolve_project_gateway_key",
            new_callable=AsyncMock,
            return_value="axm_test_key",
        ),
        patch("axiom.workers.agent_worker.EventPublisher.publish", new_callable=AsyncMock),
        patch("axiom.workers.agent_worker.Heartbeat") as hb_cls,
        patch.object(AsyncSession, "commit", flaky_commit),
    ):
        hb_cls.return_value.start = lambda: None
        hb_cls.return_value.stop = AsyncMock()
        await process_run(rid)

    async with session_scope() as db:
        row = await db.get(AgentRun, UUID(rid))
        assert row is not None
        assert row.status == "failed"