"""Evidence stage unit tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from axiom.services.crypto import aes_gcm
from axiom.services.crypto.aes_gcm import AESGCMCiphertext
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.evidence import EvidenceStage
from axiom.services.policy.evaluator import PolicyDecision, Verdict


def _ctx(action: dict | None = None) -> PipelineContext:
    ctx = PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="corr-123",
        action=action or {"type": "t", "body": "hi"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime(2026, 4, 16, 17, 0, tzinfo=UTC),
    )
    ctx.decision = PolicyDecision(
        verdict=Verdict.DENY,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target=None,
    )
    ctx.explanation = "because"
    ctx.dispatched = False
    return ctx


@pytest.mark.asyncio
async def test_evidence_encrypts_and_hashes() -> None:
    key = aes_gcm.generate_key()
    stage = EvidenceStage(evidence_key=key, evidence_key_id="kid")
    ctx = _ctx()
    result = await stage.execute(ctx)
    assert result.ok is True
    assert ctx.evidence_ciphertext is not None
    assert ctx.evidence_nonce is not None
    assert ctx.payload_hash is not None
    assert len(ctx.payload_hash) == 32


@pytest.mark.asyncio
async def test_evidence_decryptable_with_correct_key() -> None:
    key = aes_gcm.generate_key()
    stage = EvidenceStage(evidence_key=key, evidence_key_id="kid")
    ctx = _ctx({"type": "t", "body": "confidential"})
    await stage.execute(ctx)
    assert ctx.evidence_nonce is not None
    assert ctx.evidence_ciphertext is not None
    plaintext = aes_gcm.decrypt(
        key,
        AESGCMCiphertext(
            nonce=ctx.evidence_nonce,
            ciphertext=ctx.evidence_ciphertext,
            key_id="kid",
        ),
    )
    body = json.loads(plaintext.decode("utf-8"))
    assert body["action"]["body"] == "confidential"
    assert body["correlation_id"] == "corr-123"


@pytest.mark.asyncio
async def test_evidence_hash_matches_ciphertext_envelope() -> None:
    key = aes_gcm.generate_key()
    stage = EvidenceStage(evidence_key=key, evidence_key_id="kid")
    ctx = _ctx()
    await stage.execute(ctx)
    assert ctx.evidence_ciphertext is not None
    assert ctx.evidence_nonce is not None
    hasher = hashlib.sha256()
    hasher.update(ctx.evidence_nonce)
    hasher.update(ctx.evidence_ciphertext)
    hasher.update(b"kid")
    assert ctx.payload_hash == hasher.digest()


@pytest.mark.asyncio
async def test_evidence_different_actions_produce_different_hashes() -> None:
    key = aes_gcm.generate_key()
    stage = EvidenceStage(evidence_key=key, evidence_key_id="kid")
    ctx1 = _ctx({"type": "a"})
    ctx2 = _ctx({"type": "b"})
    await stage.execute(ctx1)
    await stage.execute(ctx2)
    assert ctx1.payload_hash != ctx2.payload_hash


@pytest.mark.asyncio
async def test_evidence_rejects_short_key() -> None:
    with pytest.raises(ValueError):
        EvidenceStage(evidence_key=b"short", evidence_key_id="kid")
