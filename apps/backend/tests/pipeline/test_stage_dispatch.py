"""Dispatch stage unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.dispatch import DispatchStage
from axiom.services.policy.evaluator import PolicyDecision, Verdict


def _ctx(mode: PipelineMode) -> PipelineContext:
    return PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="x",
        action={"type": "t"},
        mode=mode,
        requested_at=datetime.now(UTC),
    )


def _decision(verdict: Verdict) -> PolicyDecision:
    return PolicyDecision(
        verdict=verdict,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="x",
        modification=None,
        escalation_target="ops" if verdict is Verdict.ESCALATE else None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "verdict",
    [Verdict.APPROVE, Verdict.DENY, Verdict.MODIFY, Verdict.ESCALATE],
)
async def test_shadow_never_dispatches(verdict: Verdict) -> None:
    ctx = _ctx(PipelineMode.SHADOW)
    ctx.decision = _decision(verdict)
    result = await DispatchStage().execute(ctx)
    assert result.ok is True
    assert ctx.dispatched is False


@pytest.mark.asyncio
async def test_enforce_approve_dispatches() -> None:
    ctx = _ctx(PipelineMode.ENFORCE)
    ctx.decision = _decision(Verdict.APPROVE)
    await DispatchStage().execute(ctx)
    assert ctx.dispatched is True


@pytest.mark.asyncio
async def test_enforce_modify_dispatches() -> None:
    ctx = _ctx(PipelineMode.ENFORCE)
    ctx.decision = _decision(Verdict.MODIFY)
    await DispatchStage().execute(ctx)
    assert ctx.dispatched is True


@pytest.mark.asyncio
async def test_enforce_deny_blocks() -> None:
    ctx = _ctx(PipelineMode.ENFORCE)
    ctx.decision = _decision(Verdict.DENY)
    await DispatchStage().execute(ctx)
    assert ctx.dispatched is False


@pytest.mark.asyncio
async def test_enforce_escalate_blocks_and_records_target() -> None:
    ctx = _ctx(PipelineMode.ENFORCE)
    ctx.decision = _decision(Verdict.ESCALATE)
    await DispatchStage().execute(ctx)
    assert ctx.dispatched is False
    assert ctx.decision is not None
    assert ctx.decision.escalation_target == "ops"


@pytest.mark.asyncio
async def test_dispatch_without_decision_fails_closed() -> None:
    ctx = _ctx(PipelineMode.ENFORCE)
    result = await DispatchStage().execute(ctx)
    assert result.ok is False
    assert result.error == "dispatch_without_decision"
