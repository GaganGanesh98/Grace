"""Strategy + Authority stage tests using a real Postgres session."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.authority import AuthorityStage
from axiom.services.pipeline.stages.strategy import StrategyStage
from axiom.services.policy.evaluator import Verdict
from tests.fixtures.governance import bootstrap_project_with_api_key


def _make_ctx(project_id: UUID, action: dict) -> PipelineContext:
    return PipelineContext(
        project_id=project_id,
        agent_id=uuid4(),
        api_key_id=uuid4(),
        correlation_id="c",
        action=action,
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_strategy_selects_most_specific_policy(client: AsyncClient) -> None:
    rules = [
        {
            "id": "block_email",
            "description": "Block outbound email",
            "when": {"type": "send_email"},
            "then": "deny",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    async with session_scope() as session:
        ctx = _make_ctx(UUID(fx["project_id"]), {"type": "send_email", "to": "x"})
        res = await StrategyStage(session).execute(ctx)
        assert res.ok is True
        assert ctx.policy_id == fx["policy_id"]
        assert ctx.policy_version is not None


@pytest.mark.asyncio
async def test_strategy_falls_back_to_most_recent_when_no_specific_match(
    client: AsyncClient,
) -> None:
    rules: list[dict] = []  # no rule at all
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    async with session_scope() as session:
        ctx = _make_ctx(UUID(fx["project_id"]), {"type": "random"})
        await StrategyStage(session).execute(ctx)
        # fallback: we still pick the single existing policy
        assert ctx.policy_id == fx["policy_id"]


@pytest.mark.asyncio
async def test_authority_no_policy_denies_with_no_policy_reason(client: AsyncClient) -> None:
    async with session_scope() as session:
        ctx = _make_ctx(uuid4(), {"type": "t"})
        ctx.policy_id = None
        res = await AuthorityStage(session).execute(ctx)
        assert res.ok is True
        assert ctx.decision is not None
        assert ctx.decision.verdict == Verdict.DENY
        assert "no policy configured" in ctx.decision.reasoning


@pytest.mark.asyncio
async def test_authority_evaluates_policy_and_denies(client: AsyncClient) -> None:
    rules = [
        {
            "id": "ban_nuke",
            "description": "Never launch nukes",
            "when": {"type": "launch_nuke"},
            "then": "deny",
            "legal_citation": "Treaty NPT",
            "remediation_guidance": "Do not request nuclear launch.",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    async with session_scope() as session:
        ctx = _make_ctx(UUID(fx["project_id"]), {"type": "launch_nuke"})
        ctx.policy_id = fx["policy_id"]
        ctx.policy_version = "1"
        res = await AuthorityStage(session).execute(ctx)
        assert res.ok is True
        assert ctx.decision is not None
        assert ctx.decision.verdict == Verdict.DENY
        assert ctx.explanation is not None
        assert "Treaty NPT" in ctx.explanation
        assert "Do not request" in ctx.explanation


@pytest.mark.asyncio
async def test_authority_injection_override_when_policy_flag_set(client: AsyncClient) -> None:
    rules = [
        {
            "id": "allow_chat",
            "description": "Chat is fine",
            "when": {"type": "chat"},
            "then": "approve",
            "block_on_injection": True,
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    async with session_scope() as session:
        ctx = _make_ctx(UUID(fx["project_id"]), {"type": "chat", "body": "safe"})
        ctx.policy_id = fx["policy_id"]
        ctx.policy_version = "1"
        # Simulate an injection match seen by Stage 1
        from axiom.services.prompt_injection.detector import (
            InjectionCategory,
            InjectionMatch,
        )

        ctx.injection_matches = (
            InjectionMatch(
                category=InjectionCategory.INSTRUCTION_OVERRIDE,
                pattern_id="instruction_override_v1",
                matched_span=(0, 10),
                matched_text="Ignore all",
            ),
        )
        await AuthorityStage(session).execute(ctx)
        assert ctx.decision is not None
        assert ctx.decision.verdict == Verdict.DENY
        assert "injection" in ctx.decision.reasoning


@pytest.mark.asyncio
async def test_authority_no_injection_override_when_flag_absent(client: AsyncClient) -> None:
    rules = [
        {
            "id": "allow_chat",
            "description": "Chat is fine",
            "when": {"type": "chat"},
            "then": "approve",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    async with session_scope() as session:
        ctx = _make_ctx(UUID(fx["project_id"]), {"type": "chat", "body": "safe"})
        ctx.policy_id = fx["policy_id"]
        ctx.policy_version = "1"
        from axiom.services.prompt_injection.detector import (
            InjectionCategory,
            InjectionMatch,
        )

        ctx.injection_matches = (
            InjectionMatch(
                category=InjectionCategory.INSTRUCTION_OVERRIDE,
                pattern_id="instruction_override_v1",
                matched_span=(0, 10),
                matched_text="Ignore all",
            ),
        )
        await AuthorityStage(session).execute(ctx)
        assert ctx.decision is not None
        assert ctx.decision.verdict == Verdict.APPROVE
