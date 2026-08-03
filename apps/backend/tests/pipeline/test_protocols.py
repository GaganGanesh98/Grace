"""Protocol + dataclass contract tests for the pipeline leaf module."""

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
from axiom.services.pipeline.stages.intent import IntentStage


def _ctx() -> PipelineContext:
    return PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="corr-1",
        action={"type": "ping"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )


def test_stage_result_is_frozen() -> None:
    r = StageResult(ok=True, stage_name="x", duration_ms=1.0)
    # dataclass(frozen=True) raises FrozenInstanceError (subclass of AttributeError)
    with pytest.raises(AttributeError):
        r.ok = False  # type: ignore[misc]


def test_concrete_stage_is_protocol_conformant() -> None:
    intent = IntentStage()
    assert isinstance(intent, Stage)


def test_pipeline_mode_str_values() -> None:
    assert PipelineMode.SHADOW.value == "shadow"
    assert PipelineMode.ENFORCE.value == "enforce"


def test_pipeline_context_writable() -> None:
    ctx = _ctx()
    ctx.policy_id = "pid"
    ctx.explanation = "because"
    assert ctx.policy_id == "pid"
    assert ctx.explanation == "because"


def test_pipeline_context_stage_results_default_empty() -> None:
    ctx = _ctx()
    assert ctx.stage_results == []
