"""Unit tests for PreflightRunner."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from axiom.services.pipeline.preflight_runner import PreflightRunner
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode, StageResult
from axiom.services.policy.evaluator import PolicyDecision, Verdict


def _ctx() -> PipelineContext:
    return PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="corr",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )


def test_preflight_runner_init_rejects_wrong_stage_count() -> None:
    m1, m2 = MagicMock(), MagicMock()
    m1.name = "intent"
    m2.name = "strategy"
    with pytest.raises(ValueError, match="exactly 3"):
        PreflightRunner((m1, m2))  # type: ignore[arg-type]


def test_preflight_runner_init_rejects_wrong_stage_names() -> None:
    stages = tuple(MagicMock() for _ in range(3))
    for s, n in zip(stages, ("intent", "strategy", "dispatch"), strict=True):
        s.name = n
    with pytest.raises(ValueError, match="dispatch"):
        PreflightRunner(stages)  # type: ignore[arg-type]


def test_preflight_runner_init_rejects_wrong_stage_order() -> None:
    stages = tuple(MagicMock() for _ in range(3))
    for s, n in zip(stages, ("strategy", "intent", "authority"), strict=True):
        s.name = n
    with pytest.raises(ValueError, match="order"):
        PreflightRunner(stages)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_preflight_runner_happy_path() -> None:
    decision = PolicyDecision(
        verdict=Verdict.APPROVE,
        rule_id="r1",
        policy_id="pol",
        policy_version="1",
        reasoning="ok",
        modification=None,
        escalation_target=None,
    )

    async def intent_ok(ctx: PipelineContext) -> StageResult:
        return StageResult(ok=True, stage_name="intent", duration_ms=0.0)

    async def strat_ok(ctx: PipelineContext) -> StageResult:
        ctx.policy_id = "pol"
        ctx.policy_version = "1"
        return StageResult(ok=True, stage_name="strategy", duration_ms=0.0)

    async def auth_ok(ctx: PipelineContext) -> StageResult:
        ctx.decision = decision
        ctx.explanation = "because"
        return StageResult(ok=True, stage_name="authority", duration_ms=0.0)

    i, s, a = MagicMock(), MagicMock(), MagicMock()
    i.name, s.name, a.name = "intent", "strategy", "authority"
    i.execute, s.execute, a.execute = intent_ok, strat_ok, auth_ok

    runner = PreflightRunner((i, s, a))
    ctx = _ctx()
    out = await runner.run(ctx)
    assert out.decision == decision
    assert len(out.stage_results) == 3


@pytest.mark.asyncio
async def test_preflight_runner_fail_closed_on_intent_error() -> None:
    async def intent_bad(_: PipelineContext) -> StageResult:
        return StageResult(ok=False, stage_name="intent", duration_ms=0.0, error="bad")

    async def strat_ok(ctx: PipelineContext) -> StageResult:
        ctx.policy_id = "p"
        ctx.policy_version = "1"
        return StageResult(ok=True, stage_name="strategy", duration_ms=0.0)

    async def auth_ok(ctx: PipelineContext) -> StageResult:
        raise AssertionError("authority must not run")

    i, s, a = MagicMock(), MagicMock(), MagicMock()
    i.name, s.name, a.name = "intent", "strategy", "authority"
    i.execute, s.execute, a.execute = intent_bad, strat_ok, auth_ok

    ctx = _ctx()
    out = await PreflightRunner((i, s, a)).run(ctx)
    assert out.decision is not None
    assert out.decision.verdict == Verdict.DENY
    assert "intent" in out.decision.reasoning


@pytest.mark.asyncio
async def test_preflight_runner_fail_closed_on_strategy_error() -> None:
    async def intent_ok(_: PipelineContext) -> StageResult:
        return StageResult(ok=True, stage_name="intent", duration_ms=0.0)

    async def strat_bad(_: PipelineContext) -> StageResult:
        return StageResult(ok=False, stage_name="strategy", duration_ms=0.0, error="db")

    i, s, a = MagicMock(), MagicMock(), MagicMock()
    i.name, s.name, a.name = "intent", "strategy", "authority"
    i.execute, s.execute, a.execute = intent_ok, strat_bad, AsyncMock()

    ctx = _ctx()
    out = await PreflightRunner((i, s, a)).run(ctx)
    assert out.decision is not None
    assert out.decision.verdict == Verdict.DENY
    assert "strategy" in out.decision.reasoning


@pytest.mark.asyncio
async def test_preflight_runner_fail_closed_on_authority_error() -> None:
    async def intent_ok(_: PipelineContext) -> StageResult:
        return StageResult(ok=True, stage_name="intent", duration_ms=0.0)

    async def strat_ok(ctx: PipelineContext) -> StageResult:
        ctx.policy_id = "p"
        ctx.policy_version = "1"
        return StageResult(ok=True, stage_name="strategy", duration_ms=0.0)

    async def auth_bad(_: PipelineContext) -> StageResult:
        return StageResult(ok=False, stage_name="authority", duration_ms=0.0, error="boom")

    i, s, a = MagicMock(), MagicMock(), MagicMock()
    i.name, s.name, a.name = "intent", "strategy", "authority"
    i.execute, s.execute, a.execute = intent_ok, strat_ok, auth_bad

    ctx = _ctx()
    out = await PreflightRunner((i, s, a)).run(ctx)
    assert out.decision is not None
    assert out.decision.verdict == Verdict.DENY


@pytest.mark.asyncio
async def test_preflight_runner_fail_closed_on_intent_exception() -> None:
    async def intent_raise(_: PipelineContext) -> StageResult:
        raise RuntimeError("nope")

    async def strat_raise(_: PipelineContext) -> StageResult:
        raise AssertionError("strategy must not run after intent failure")

    async def auth_raise(_: PipelineContext) -> StageResult:
        raise AssertionError("authority must not run")

    i, s, a = MagicMock(), MagicMock(), MagicMock()
    i.name, s.name, a.name = "intent", "strategy", "authority"
    i.execute, s.execute, a.execute = intent_raise, strat_raise, auth_raise

    ctx = _ctx()
    out = await PreflightRunner((i, s, a)).run(ctx)
    assert out.decision is not None
    assert out.decision.verdict == Verdict.DENY
    assert out.receipt_id is None
    assert out.signature is None


@pytest.mark.asyncio
async def test_preflight_runner_does_not_call_dispatch_evidence_receipt() -> None:
    called: list[str] = []

    async def intent_ok(_: PipelineContext) -> StageResult:
        called.append("intent")
        return StageResult(ok=True, stage_name="intent", duration_ms=0.0)

    async def strat_ok(ctx: PipelineContext) -> StageResult:
        called.append("strategy")
        ctx.policy_id = "p"
        ctx.policy_version = "1"
        return StageResult(ok=True, stage_name="strategy", duration_ms=0.0)

    async def auth_ok(ctx: PipelineContext) -> StageResult:
        called.append("authority")
        ctx.decision = PolicyDecision(
            verdict=Verdict.APPROVE,
            rule_id="x",
            policy_id="p",
            policy_version="1",
            reasoning="r",
            modification=None,
            escalation_target=None,
        )
        return StageResult(ok=True, stage_name="authority", duration_ms=0.0)

    i, s, a = MagicMock(), MagicMock(), MagicMock()
    i.name, s.name, a.name = "intent", "strategy", "authority"
    i.execute, s.execute, a.execute = intent_ok, strat_ok, auth_ok

    await PreflightRunner((i, s, a)).run(_ctx())
    assert called == ["intent", "strategy", "authority"]
