"""Intent declaration (stage 1)."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from axiom.db import session_scope
from axiom.models.governance import GovernanceIntent
from axiom.schemas.governance import GovernRequest
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import clear_policy_cache_for_tests
from axiom.services.governance.receipt import reset_governance_merkle_for_tests
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.fixture(autouse=True)
def _reset_merkle_and_policy() -> None:
    clear_policy_cache_for_tests()
    reset_governance_merkle_for_tests()
    yield
    reset_governance_merkle_for_tests()
    clear_policy_cache_for_tests()


@pytest.mark.asyncio
async def test_intent_creation_stores_agent_action_target_and_risk(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        body = GovernRequest(
            agent_id="agent-alpha",
            action_type="tool.db.query",
            target="postgres://cluster/db",
            risk="medium",
            metadata={"correlation_id": "corr-123"},
        )
        intent = await declare_intent(session, pid, body)
        await session.commit()
        assert intent.agent_id == "agent-alpha"
        assert intent.action_type == "tool.db.query"
        assert intent.target == "postgres://cluster/db"
        assert intent.risk_declared == "medium"
        assert intent.extra_metadata.get("correlation_id") == "corr-123"


@pytest.mark.asyncio
async def test_intent_links_to_project(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        body = GovernRequest(
            agent_id="a",
            action_type="t",
            target="https://x",
            risk="low",
        )
        intent = await declare_intent(session, pid, body)
        await session.commit()
        assert intent.project_id == pid


@pytest.mark.asyncio
async def test_duplicate_intent_creates_distinct_rows(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        body = GovernRequest(
            agent_id="dup",
            action_type="same",
            target="https://dup",
            risk="low",
        )
        i1 = await declare_intent(session, pid, body)
        i2 = await declare_intent(session, pid, body)
        await session.commit()
        assert i1.id != i2.id

    async with session_scope() as session:
        rows = await session.scalars(
            select(GovernanceIntent).where(
                GovernanceIntent.project_id == pid,
                GovernanceIntent.agent_id == "dup",
            )
        )
        assert len(rows.all()) == 2
