"""Hypothesis property tests for pre-flight."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from axiom.services.pipeline.preflight_runner import PreflightRunner
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode, StageResult
from axiom.services.policy.evaluator import Verdict
from axiom.services.preflight.cache import PreflightCache


@given(
    st.text(min_size=1, max_size=12),
    st.text(min_size=1, max_size=12),
    st.text(min_size=1, max_size=12),
    st.text(min_size=1, max_size=12),
    st.text(min_size=1, max_size=12),
    st.text(min_size=64, max_size=64, alphabet="abcdef0123456789"),
    st.sampled_from(["enforce", "shadow"]),
)
def test_hypothesis_cache_keys_differ_when_any_component_differs(
    project_id: str,
    policy_id: str,
    policy_version: str,
    agent_id: str,
    api_key_id: str,
    action_hash: str,
    mode: str,
) -> None:
    def kw(**overrides: str) -> dict[str, str]:
        base = {
            "project_id": project_id,
            "policy_id": policy_id,
            "policy_version": policy_version,
            "agent_id": agent_id,
            "api_key_id": api_key_id,
            "action_canonical_hash_hex": action_hash,
            "mode": mode,
        }
        base.update(overrides)
        return base

    k0 = PreflightCache._compute_key(**kw())
    assert PreflightCache._compute_key(**kw(project_id=project_id + "_mut")) != k0
    assert PreflightCache._compute_key(**kw(policy_id=policy_id + "_x")) != k0
    assert PreflightCache._compute_key(**kw(policy_version=policy_version + "_x")) != k0
    assert PreflightCache._compute_key(**kw(agent_id=agent_id + "_x")) != k0
    assert PreflightCache._compute_key(**kw(api_key_id=api_key_id + "_x")) != k0
    flip = action_hash[:-1] + ("0" if action_hash[-1] != "0" else "1")
    assert PreflightCache._compute_key(**kw(action_canonical_hash_hex=flip)) != k0
    alt_mode = "shadow" if mode == "enforce" else "enforce"
    assert PreflightCache._compute_key(**kw(mode=alt_mode)) != k0


@pytest.mark.asyncio
async def test_hypothesis_preflight_runner_exception_is_deny() -> None:
    async def boom(_: PipelineContext) -> StageResult:
        raise RuntimeError("x")

    async def never(_: PipelineContext) -> StageResult:
        raise AssertionError("should not run")

    i, s, a = MagicMock(), MagicMock(), MagicMock()
    i.name, s.name, a.name = "intent", "strategy", "authority"
    i.execute, s.execute, a.execute = boom, never, never

    from uuid import uuid4

    ctx = PipelineContext(
        project_id=uuid4(),
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="c",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )
    out = await PreflightRunner((i, s, a)).run(ctx)
    assert out.decision is not None
    assert out.decision.verdict == Verdict.DENY
    assert out.receipt_id is None
    assert out.signature is None
