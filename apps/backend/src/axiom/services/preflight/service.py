"""PreflightService — orchestrates cache + runner + confidence labeling."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.policy import Policy as PolicyModel
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.pipeline.preflight_runner import PreflightRunner
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.stages.authority import AuthorityStage
from axiom.services.pipeline.stages.intent import IntentStage
from axiom.services.pipeline.stages.strategy import StrategyStage
from axiom.services.policy.evaluator import PolicyRule, Verdict
from axiom.services.preflight.cache import PreflightCache
from axiom.services.preflight.confidence import (
    PreflightConfidence,
    compute_confidence,
    is_rule_deterministic,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PreflightPrediction:
    predicted_verdict: Verdict
    rule_id: str | None
    policy_id: str
    policy_version: str
    reasoning: str
    explanation: str
    probably_definitive: bool
    confidence: PreflightConfidence
    cached: bool
    cache_age_seconds: int | None
    prediction_id: str  # unique per call, for logging/correlation
    correlation_id: str


def build_preflight_runner(session: AsyncSession) -> PreflightRunner:
    """Compose Intent → Strategy → Authority for prediction-only runs."""

    return PreflightRunner(
        stages=(
            IntentStage(),
            StrategyStage(session),
            AuthorityStage(session),
        ),
    )


class PreflightService:
    def __init__(self, cache: PreflightCache) -> None:
        self._cache = cache

    async def predict(
        self,
        session: AsyncSession,
        project_id: UUID,
        agent_id: UUID,
        api_key_id: UUID,
        action: dict[str, object],
        mode: PipelineMode,
    ) -> PreflightPrediction:
        correlation_id = f"pf_{uuid4().hex[:16]}"
        prediction_id = f"pred_{uuid4().hex}"

        action_canonical = canonicalize(action)
        action_hash_hex = hashlib.sha256(action_canonical).hexdigest()

        ctx = PipelineContext(
            project_id=project_id,
            agent_id=agent_id,
            api_key_id=api_key_id,
            correlation_id=correlation_id,
            action=action,
            mode=mode,
            requested_at=datetime.now(UTC),
            action_canonical=action_canonical,
        )

        runner = build_preflight_runner(session)
        strategy_stage = next(s for s in runner._stages if s.name == "strategy")
        strategy_result = await strategy_stage.execute(ctx)
        if not strategy_result.ok:
            return self._build_fail_closed_prediction(
                ctx=ctx,
                reason=f"strategy stage error: {strategy_result.error}",
                prediction_id=prediction_id,
                correlation_id=correlation_id,
            )

        if ctx.policy_id is None:
            return self._build_fail_closed_prediction(
                ctx=ctx,
                reason="no policy configured for this action type",
                prediction_id=prediction_id,
                correlation_id=correlation_id,
            )

        try:
            cache_result = await self._cache.get(
                project_id=str(project_id),
                policy_id=ctx.policy_id,
                policy_version=ctx.policy_version or "0",
                agent_id=str(agent_id),
                api_key_id=str(api_key_id),
                action_canonical_hash_hex=action_hash_hex,
                mode=mode.value,
            )
        except Exception:  # noqa: BLE001
            logger.warning("preflight_cache_get_unexpected", exc_info=True)
            cache_result = None
        if cache_result is not None:
            cached, age = cache_result
            confidence = compute_confidence(
                cache_hit=True,
                cache_age_seconds=age,
                rule_is_deterministic=cached.probably_definitive,
            )
            logger.info(
                "preflight_cache_hit",
                correlation_id=correlation_id,
                prediction_id=prediction_id,
                age_seconds=age,
            )
            return PreflightPrediction(
                predicted_verdict=Verdict(cached.predicted_verdict),
                rule_id=cached.rule_id,
                policy_id=cached.policy_id,
                policy_version=cached.policy_version,
                reasoning=cached.reasoning,
                explanation=cached.explanation,
                probably_definitive=cached.probably_definitive,
                confidence=confidence,
                cached=True,
                cache_age_seconds=age,
                prediction_id=prediction_id,
                correlation_id=correlation_id,
            )

        intent_stage = next(s for s in runner._stages if s.name == "intent")
        authority_stage = next(s for s in runner._stages if s.name == "authority")

        intent_result = await intent_stage.execute(ctx)
        if not intent_result.ok:
            return self._build_fail_closed_prediction(
                ctx=ctx,
                reason=f"intent stage error: {intent_result.error}",
                prediction_id=prediction_id,
                correlation_id=correlation_id,
            )

        authority_result = await authority_stage.execute(ctx)
        if not authority_result.ok or ctx.decision is None:
            return self._build_fail_closed_prediction(
                ctx=ctx,
                reason=f"authority stage error: {authority_result.error}",
                prediction_id=prediction_id,
                correlation_id=correlation_id,
            )

        rule = await self._lookup_rule(session, ctx.policy_id, ctx.decision.rule_id)
        probably_definitive = is_rule_deterministic(rule)
        confidence = compute_confidence(
            cache_hit=False,
            cache_age_seconds=0,
            rule_is_deterministic=probably_definitive,
        )

        try:
            await self._cache.set(
                project_id=str(project_id),
                policy_id=ctx.policy_id,
                policy_version=ctx.policy_version or "0",
                agent_id=str(agent_id),
                api_key_id=str(api_key_id),
                action_canonical_hash_hex=action_hash_hex,
                mode=mode.value,
                prediction_data={
                    "predicted_verdict": ctx.decision.verdict.value,
                    "rule_id": ctx.decision.rule_id,
                    "policy_id": ctx.decision.policy_id,
                    "policy_version": ctx.decision.policy_version,
                    "reasoning": ctx.decision.reasoning,
                    "explanation": ctx.explanation or "",
                    "probably_definitive": probably_definitive,
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning("preflight_cache_set_unexpected", exc_info=True)

        logger.info(
            "preflight_fresh",
            correlation_id=correlation_id,
            prediction_id=prediction_id,
            verdict=ctx.decision.verdict.value,
        )

        return PreflightPrediction(
            predicted_verdict=ctx.decision.verdict,
            rule_id=ctx.decision.rule_id,
            policy_id=ctx.decision.policy_id,
            policy_version=ctx.decision.policy_version,
            reasoning=ctx.decision.reasoning,
            explanation=ctx.explanation or "",
            probably_definitive=probably_definitive,
            confidence=confidence,
            cached=False,
            cache_age_seconds=None,
            prediction_id=prediction_id,
            correlation_id=correlation_id,
        )

    def _build_fail_closed_prediction(
        self,
        *,
        ctx: PipelineContext,
        reason: str,
        prediction_id: str,
        correlation_id: str,
    ) -> PreflightPrediction:
        """Used when any preflight stage fails. Always DENY, always HIGH confidence in the DENY."""
        return PreflightPrediction(
            predicted_verdict=Verdict.DENY,
            rule_id=None,
            policy_id=ctx.policy_id or "UNKNOWN",
            policy_version=ctx.policy_version or "0.0.0",
            reasoning=reason,
            explanation="Pre-flight check indicates this action would be denied.",
            probably_definitive=True,
            confidence=PreflightConfidence.HIGH,
            cached=False,
            cache_age_seconds=None,
            prediction_id=prediction_id,
            correlation_id=correlation_id,
        )

    async def _lookup_rule(
        self,
        session: AsyncSession,
        policy_id: str,
        rule_id: str | None,
    ) -> PolicyRule | None:
        """Loads PolicyRule from DB by (policy_id, rule_id). Returns None if rule_id is None."""
        if rule_id is None:
            return None
        row = await session.get(PolicyModel, UUID(policy_id))
        if row is None:
            return None
        rules = row.rules if isinstance(row.rules, list) else []
        for raw in rules:
            if not isinstance(raw, dict):
                continue
            if str(raw.get("id", "")) != rule_id:
                continue
            try:
                return PolicyRule.model_validate(
                    {
                        "id": str(raw.get("id", "")),
                        "description": str(raw.get("description", "")),
                        "when": raw.get("when", {}) if isinstance(raw.get("when"), dict) else {},
                        "then": raw.get("then", "deny"),
                        "modification": raw.get("modification"),
                        "escalation_target": raw.get("escalation_target"),
                    }
                )
            except (TypeError, ValueError, KeyError, ValidationError):
                return None
        return None
