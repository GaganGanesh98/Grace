"""PipelineRunner unit tests — fail-closed invariant, ordering, stage routing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from axiom.services.pipeline.protocols import (
    PipelineContext,
    PipelineMode,
    Stage,
    StageResult,
)
from axiom.services.pipeline.runner import PipelineRunner
from axiom.services.policy.evaluator import PolicyDecision, Verdict


class _RecordingStage:
    def __init__(self, name: str, *, fail: bool = False, raise_exc: bool = False) -> None:
        self.name = name
        self._fail = fail
        self._raise = raise_exc
        self.called = False

    async def execute(self, ctx: PipelineContext) -> StageResult:
        _ = ctx
        self.called = True
        if self._raise:
            raise RuntimeError(f"boom in {self.name}")
        if self._fail:
            return StageResult(ok=False, stage_name=self.name, duration_ms=0.1, error="nope")
        return StageResult(ok=True, stage_name=self.name, duration_ms=0.1)


class _SucceedingEvidence(_RecordingStage):
    def __init__(self) -> None:
        super().__init__("evidence")

    async def execute(self, ctx: PipelineContext) -> StageResult:
        self.called = True
        ctx.payload_hash = b"\x00" * 32
        return StageResult(ok=True, stage_name=self.name, duration_ms=0.1)


class _SucceedingReceipt(_RecordingStage):
    def __init__(self) -> None:
        super().__init__("receipt")

    async def execute(self, ctx: PipelineContext) -> StageResult:
        self.called = True
        ctx.receipt_id = "rcpt_ok"
        ctx.merkle_root = b"\x01" * 32
        ctx.merkle_tree_size = 1
        ctx.merkle_leaf_index = 0
        return StageResult(ok=True, stage_name=self.name, duration_ms=0.1)


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


def _healthy_stages() -> tuple[Stage, ...]:
    return (
        _RecordingStage("intent"),
        _RecordingStage("strategy"),
        _RecordingStage("authority"),
        _RecordingStage("dispatch"),
        _SucceedingEvidence(),
        _SucceedingReceipt(),
    )


def test_runner_rejects_wrong_count() -> None:
    with pytest.raises(ValueError):
        PipelineRunner(stages=(_RecordingStage("intent"),))


def test_runner_rejects_wrong_order() -> None:
    with pytest.raises(ValueError):
        PipelineRunner(
            stages=(
                _RecordingStage("strategy"),
                _RecordingStage("intent"),
                _RecordingStage("authority"),
                _RecordingStage("dispatch"),
                _SucceedingEvidence(),
                _SucceedingReceipt(),
            )
        )


@pytest.mark.asyncio
async def test_runner_healthy_path_executes_all_in_order() -> None:
    stages = _healthy_stages()
    runner = PipelineRunner(stages=stages)
    ctx = _ctx()
    ctx.decision = PolicyDecision(
        verdict=Verdict.APPROVE,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="ok",
        modification=None,
        escalation_target=None,
    )
    out = await runner.run(ctx)
    assert [r.stage_name for r in out.stage_results] == [
        "intent",
        "strategy",
        "authority",
        "dispatch",
        "evidence",
        "receipt",
    ]
    assert all(r.ok for r in out.stage_results)


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_stage", ["intent", "strategy", "authority", "dispatch"])
async def test_runner_stage_failure_forces_deny_but_still_produces_receipt(
    failing_stage: str,
) -> None:
    stages = list(_healthy_stages())
    idx = next(i for i, s in enumerate(stages) if s.name == failing_stage)
    stages[idx] = _RecordingStage(failing_stage, fail=True)
    runner = PipelineRunner(stages=tuple(stages))
    ctx = _ctx()
    out = await runner.run(ctx)
    assert out.decision is not None
    assert out.decision.verdict == Verdict.DENY
    assert "pipeline stage error" in out.decision.reasoning
    assert out.receipt_id == "rcpt_ok"
    assert out.merkle_root is not None
    assert any(not r.ok for r in out.stage_results)


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_stage", ["intent", "strategy", "authority", "dispatch"])
async def test_runner_stage_exception_is_caught_and_denies(failing_stage: str) -> None:
    stages = list(_healthy_stages())
    idx = next(i for i, s in enumerate(stages) if s.name == failing_stage)
    stages[idx] = _RecordingStage(failing_stage, raise_exc=True)
    runner = PipelineRunner(stages=tuple(stages))
    ctx = _ctx()
    out = await runner.run(ctx)
    assert out.decision is not None
    assert out.decision.verdict == Verdict.DENY
    assert out.receipt_id == "rcpt_ok"


@pytest.mark.asyncio
async def test_runner_evidence_failure_stops_and_no_receipt() -> None:
    stages = list(_healthy_stages())

    # Replace evidence with a failing one
    class _FailEvidence(_RecordingStage):
        def __init__(self) -> None:
            super().__init__("evidence", fail=True)

    stages[4] = _FailEvidence()
    runner = PipelineRunner(stages=tuple(stages))
    ctx = _ctx()
    ctx.decision = PolicyDecision(
        verdict=Verdict.APPROVE,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="ok",
        modification=None,
        escalation_target=None,
    )
    out = await runner.run(ctx)
    assert out.receipt_id is None
    assert not stages[5].called  # receipt not called
