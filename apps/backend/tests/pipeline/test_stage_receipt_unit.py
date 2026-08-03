"""Receipt stage coverage: missing precondition, exception branch."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.receipt import ReceiptStage


class _StubSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("stub session cannot execute")

    async def flush(self) -> None:
        return None


def _ctx() -> PipelineContext:
    return PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="c",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )


def _stage() -> ReceiptStage:
    ed = ed25519.generate_keypair()
    ml = ml_dsa.generate_keypair()
    return ReceiptStage(
        _StubSession(),  # type: ignore[arg-type]
        ed25519_private=ed.private_key_pem,
        ed25519_public=ed.public_key_pem,
        ml_dsa_private=ml.private_key_bytes,
        ml_dsa_public=ml.public_key_bytes,
    )


@pytest.mark.asyncio
async def test_receipt_stage_without_evidence_fails_fast() -> None:
    stage = _stage()
    ctx = _ctx()
    # payload_hash is None
    result = await stage.execute(ctx)
    assert result.ok is False
    assert result.error == "receipt_without_evidence_or_decision"


@pytest.mark.asyncio
async def test_receipt_stage_without_decision_fails_fast() -> None:
    stage = _stage()
    ctx = _ctx()
    ctx.payload_hash = b"\x00" * 32
    # decision is None
    result = await stage.execute(ctx)
    assert result.ok is False


@pytest.mark.asyncio
async def test_receipt_stage_catches_db_exception() -> None:
    """Stub session raises on execute → stage returns ok=False with fail-closed error."""

    from axiom.services.policy.evaluator import PolicyDecision, Verdict

    stage = _stage()
    ctx = _ctx()
    ctx.payload_hash = b"\x00" * 32
    ctx.decision = PolicyDecision(
        verdict=Verdict.APPROVE,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target=None,
    )
    result = await stage.execute(ctx)
    assert result.ok is False
    assert result.error is not None
    assert "receipt_failed" in result.error
