"""Verdict persistence matches policy engine output."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import clear_policy_cache_for_tests, evaluate_policy
from axiom.services.governance.receipt import reset_governance_merkle_for_tests
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
async def test_verdict_persisted_matches_allow_policy(client: AsyncClient) -> None:
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
            target="https://allow.example",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        await session.commit()
        assert verdict.verdict == pr.verdict == "allow"
        assert verdict.policy_version == pr.policy_version
        assert verdict.rules_evaluated == pr.rules_evaluated


@pytest.mark.asyncio
async def test_verdict_persisted_matches_deny_policy(client: AsyncClient) -> None:
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
            action_type="tool",
            target="https://deny",
            risk="critical",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        await session.commit()
        assert verdict.verdict == "deny"
        assert pr.verdict == "deny"


@pytest.mark.asyncio
async def test_verdict_persisted_matches_hold_policy(client: AsyncClient) -> None:
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
            action_type="tool",
            target="https://hold",
            risk="high",
        )
        intent = await declare_intent(session, pid, body)
        ctx = await enrich_context(session, intent)
        pr = evaluate_policy(intent, ctx)
        verdict = await render_verdict(session, intent, pr, ctx)
        await session.commit()
        assert verdict.verdict == "hold"
        assert pr.verdict == "hold"
