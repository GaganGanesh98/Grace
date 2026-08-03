"""Context enrichment for policy evaluation."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceReceipt
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
from axiom.services.governance.receipt import create_pending_receipt, reset_governance_merkle_for_tests
from axiom.services.governance.verdict import render_verdict
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_enrich_context_includes_project_settings(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "read-only"
        s["custom_flag"] = True
        project.settings = s
        body = GovernRequest(
            agent_id="ctx",
            action_type="t",
            target="https://ctx",
            risk="low",
            metadata={"correlation_id": "cid-xyz"},
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        await session.commit()
        assert ctx["project_settings"].get("governance_policy") == "read-only"
        assert ctx["project_settings"].get("custom_flag") is True


@pytest.mark.asyncio
async def test_intent_metadata_correlation_available_on_intent_row(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        body = GovernRequest(
            agent_id="ctx",
            action_type="t",
            target="https://ctx",
            risk="low",
            metadata={"correlation_id": "corr-abc"},
        )
        intent = await declare_intent(session, pid, body)
        await session.commit()
        assert intent.extra_metadata.get("correlation_id") == "corr-abc"


@pytest.mark.asyncio
async def test_context_links_intent_to_receipt_via_ids(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        body = GovernRequest(
            agent_id="link",
            action_type="tool.http.get",
            target="https://link",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        receipt = await create_pending_receipt(session, intent=intent, verdict=verdict)
        await session.commit()
        assert receipt.intent_id == intent.id
        assert receipt.verdict_id == verdict.id

    async with session_scope() as session:
        loaded = await session.get(GovernanceReceipt, receipt.id)
        assert loaded is not None
        assert loaded.intent_id == intent.id
