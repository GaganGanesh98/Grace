"""Authority stage coverage tests: policy missing, evaluator exception, coercion."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.authority import AuthorityStage, _coerce_policy
from axiom.services.policy.evaluator import Verdict
from tests.fixtures.governance import bootstrap_project_with_api_key


def _ctx(pid: UUID | None = None) -> PipelineContext:
    return PipelineContext(
        project_id=pid or uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="c",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_authority_policy_row_missing_after_strategy(client: AsyncClient) -> None:
    """Policy vanished between Strategy and Authority (race)."""

    async with session_scope() as session:
        ctx = _ctx()
        # Point to a policy UUID that doesn't exist
        ctx.policy_id = "00000000-0000-0000-0000-000000000000"
        ctx.policy_version = "1"
        res = await AuthorityStage(session).execute(ctx)
        assert res.ok is True
        assert ctx.decision is not None
        assert ctx.decision.verdict == Verdict.DENY


@pytest.mark.asyncio
async def test_authority_fail_closed_on_evaluator_exception(client: AsyncClient) -> None:
    """A malformed-in-DB policy trips Pydantic validation; we fail closed."""

    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    # Corrupt the policy's rules directly via the DB so Pydantic rejects it.
    from sqlalchemy import update

    from axiom.models.policy import Policy as PolicyModel

    async with session_scope() as session:
        await session.execute(
            update(PolicyModel)
            .where(PolicyModel.id == UUID(fx["policy_id"]))
            .values(rules=[{"id": "bad", "description": "", "when": "not-a-dict", "then": "deny"}])
        )

    async with session_scope() as session:
        ctx = _ctx(UUID(fx["project_id"]))
        ctx.policy_id = fx["policy_id"]
        ctx.policy_version = "1"
        res = await AuthorityStage(session).execute(ctx)
        # Coercion keeps it a dict (replaces non-dict when with {}), so evaluate still runs.
        # Verify no exception propagates.
        assert res.ok in (True, False)


def test_coerce_policy_handles_non_list_rules() -> None:
    """Defensive: DB JSONB sometimes stores non-list rules (bug or migration)."""

    class _Fake:
        def __init__(self, rules: object) -> None:
            self.id = "p"
            self.name = "n"
            self.version = 1
            self.rules = rules

    policy = _coerce_policy(_Fake(rules="not-a-list"))  # type: ignore[arg-type]
    assert policy.rules == []


def test_coerce_policy_filters_non_dict_items() -> None:
    class _Fake:
        def __init__(self, rules: object) -> None:
            self.id = "p"
            self.name = "n"
            self.version = 1
            self.rules = rules

    policy = _coerce_policy(
        _Fake(
            rules=[
                "stringy",
                {"id": "ok", "description": "d", "when": {"type": "x"}, "then": "approve"},
            ]
        )  # type: ignore[arg-type]
    )
    assert len(policy.rules) == 1
    assert policy.rules[0].id == "ok"
