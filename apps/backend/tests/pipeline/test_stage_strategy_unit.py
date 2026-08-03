"""Focused unit tests for the strategy stage's rule-cover helper and edge paths."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.strategy import (
    StrategyStage,
    _rules_cover_action_type,
)
from tests.fixtures.governance import bootstrap_project_with_api_key


def test_rules_cover_plain_type() -> None:
    assert _rules_cover_action_type([{"when": {"type": "chat"}}], "chat") is True


def test_rules_cover_op_eq() -> None:
    assert (
        _rules_cover_action_type([{"when": {"type": {"op": "eq", "value": "email"}}}], "email")
        is True
    )


def test_rules_cover_op_in() -> None:
    assert (
        _rules_cover_action_type([{"when": {"type": {"op": "in", "value": ["a", "b"]}}}], "b")
        is True
    )


def test_rules_cover_op_in_value_not_list() -> None:
    assert (
        _rules_cover_action_type([{"when": {"type": {"op": "in", "value": "not-a-list"}}}], "b")
        is False
    )


def test_rules_cover_no_match() -> None:
    assert _rules_cover_action_type([{"when": {"type": "email"}}], "chat") is False


def test_rules_cover_non_list_rules() -> None:
    assert _rules_cover_action_type("not a list", "chat") is False


def test_rules_cover_non_dict_item() -> None:
    assert _rules_cover_action_type(["string_rule"], "chat") is False


def test_rules_cover_when_not_dict() -> None:
    assert _rules_cover_action_type([{"when": "not-dict"}], "chat") is False


def test_rules_cover_no_type_predicate() -> None:
    assert _rules_cover_action_type([{"when": {"other": "x"}}], "chat") is False


@pytest.mark.asyncio
async def test_strategy_no_active_policy_leaves_policy_id_none(client: AsyncClient) -> None:
    # Bootstrap creates a policy by default, but we can simulate "no policies"
    # by using a fresh project_id that has no policies at all.
    async with session_scope() as session:
        ctx = PipelineContext(
            project_id=uuid4(),  # non-existent project
            agent_id=uuid4(),
            api_key_id=uuid4(),
            correlation_id="c",
            action={"type": "t"},
            mode=PipelineMode.ENFORCE,
            requested_at=datetime.now(UTC),
        )
        res = await StrategyStage(session).execute(ctx)
        assert res.ok is True
        assert ctx.policy_id is None
        assert ctx.policy_version is None


@pytest.mark.asyncio
async def test_strategy_picks_specific_over_generic(client: AsyncClient) -> None:
    rules_specific = [
        {
            "id": "r-email",
            "description": "email rule",
            "when": {"type": "email"},
            "then": "deny",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules_specific)
    from uuid import UUID

    async with session_scope() as session:
        ctx = PipelineContext(
            project_id=UUID(fx["project_id"]),
            agent_id=uuid4(),
            api_key_id=uuid4(),
            correlation_id="c",
            action={"type": "email"},
            mode=PipelineMode.ENFORCE,
            requested_at=datetime.now(UTC),
        )
        await StrategyStage(session).execute(ctx)
        assert ctx.policy_id == fx["policy_id"]


@pytest.mark.asyncio
async def test_strategy_db_error_fails_closed() -> None:
    """A DB error surfaces as StageResult(ok=False) rather than propagating."""

    class _ExplodingSession:
        async def scalars(self, *_args, **_kwargs):
            raise RuntimeError("db is down")

    ctx = PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="c",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )
    stage = StrategyStage(_ExplodingSession())  # type: ignore[arg-type]
    res = await stage.execute(ctx)
    assert res.ok is False
    assert res.error is not None
    assert "policy_lookup_failed" in res.error
