"""Evidence stage: catch-closed branch coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from axiom.services.crypto import aes_gcm
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.evidence import EvidenceStage
from axiom.services.policy.evaluator import PolicyDecision, Verdict


def _ctx() -> PipelineContext:
    ctx = PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="c",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )
    ctx.decision = PolicyDecision(
        verdict=Verdict.APPROVE,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target=None,
    )
    return ctx


@pytest.mark.asyncio
async def test_evidence_fails_closed_on_canonicalize_error() -> None:
    """If canonicalize raises, we return ok=False and never poison ctx."""

    key = aes_gcm.generate_key()
    stage = EvidenceStage(evidence_key=key, evidence_key_id="kid")
    ctx = _ctx()

    with patch(
        "axiom.services.pipeline.stages.evidence.canonicalize",
        side_effect=TypeError("unsupported"),
    ):
        res = await stage.execute(ctx)
    assert res.ok is False
    assert res.error is not None
    assert "evidence_build_failed" in res.error
    assert ctx.evidence_ciphertext is None
    assert ctx.payload_hash is None
