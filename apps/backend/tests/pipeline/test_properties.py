"""Hypothesis property tests: fail-closed invariant + Merkle round-trip."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom.services.crypto.merkle import (
    InclusionProof,
    build_tree,
    inclusion_proof,
    verify_inclusion,
)
from axiom.services.pipeline.protocols import (
    PipelineContext,
    PipelineMode,
    StageResult,
)
from axiom.services.pipeline.runner import PipelineRunner
from axiom.services.policy.evaluator import Verdict


class _RaisingStage:
    def __init__(self, name: str, *, raise_at: str | None) -> None:
        self.name = name
        self._raise_at = raise_at

    async def execute(self, ctx: PipelineContext) -> StageResult:
        if self._raise_at == self.name:
            raise RuntimeError(f"boom at {self.name}")
        if self.name == "evidence":
            ctx.payload_hash = b"\x00" * 32
        if self.name == "receipt":
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
        correlation_id="c",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
@given(where=st.sampled_from(["intent", "strategy", "authority", "dispatch"]))
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_any_stage_exception_yields_deny_and_receipt(where: str) -> None:
    stages = tuple(
        _RaisingStage(name, raise_at=where)
        for name in ("intent", "strategy", "authority", "dispatch", "evidence", "receipt")
    )
    runner = PipelineRunner(stages=stages)
    ctx = await runner.run(_ctx())
    assert ctx.decision is not None
    assert ctx.decision.verdict == Verdict.DENY
    assert ctx.receipt_id == "rcpt_ok"
    assert ctx.merkle_root is not None


@given(
    leaves=st.lists(
        st.binary(min_size=32, max_size=32),
        min_size=1,
        max_size=64,
        unique=True,
    )
)
@settings(deadline=None, max_examples=30)
def test_property_merkle_round_trip(leaves: list[bytes]) -> None:
    tree = build_tree(leaves)
    for i, leaf in enumerate(leaves):
        proof = inclusion_proof(tree, i)
        assert verify_inclusion(tree.root, leaf, proof) is True
        # Tamper root: verification must fail
        bad_root = bytes((tree.root[0] ^ 0x01,)) + tree.root[1:]
        assert verify_inclusion(bad_root, leaf, proof) is False


@given(
    leaves=st.lists(
        st.binary(min_size=32, max_size=32),
        min_size=2,
        max_size=16,
        unique=True,
    )
)
@settings(deadline=None, max_examples=20)
def test_property_wrong_leaf_fails_verification(leaves: list[bytes]) -> None:
    tree = build_tree(leaves)
    proof = inclusion_proof(tree, 0)
    other = leaves[1]
    # Using a different leaf against leaf[0]'s proof must fail.
    bad_proof = InclusionProof(
        leaf_index=proof.leaf_index,
        tree_size=proof.tree_size,
        path=proof.path,
    )
    assert verify_inclusion(tree.root, other, bad_proof) is False
