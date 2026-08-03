"""Stage 3 (Authority): run the policy evaluator + build the human-readable explanation.

Responsibility:
  * Load the DB Policy row referenced by Stage 2.
  * Coerce it into the evaluator's Pydantic ``Policy`` model.
  * Invoke ``evaluate(...)`` to produce a ``PolicyDecision``.
  * Call the ``ExplanationEngine`` to compose a sentence (legal citation +
    remediation when available).
  * If Stage 1 detected prompt injection AND the policy has
    ``block_on_injection=true`` in its rules metadata, override the verdict
    to DENY before returning.

When ``ctx.policy_id`` is None (no applicable policy), we construct a
synthetic default-DENY decision with ``reasoning="no policy configured"``.
This is a product requirement: the engine must always produce a verdict,
never a silent pass-through.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.policy import Policy as PolicyModel
from axiom.services.explanation.engine import ExplanationEngine
from axiom.services.pipeline.protocols import PipelineContext, StageResult
from axiom.services.policy.evaluator import Policy, PolicyDecision, Verdict, evaluate


def _coerce_policy(row: PolicyModel) -> Policy:
    rules = row.rules if isinstance(row.rules, list) else []
    clean_rules: list[dict[str, Any]] = []
    for raw in rules:
        if not isinstance(raw, dict):
            continue
        clean_rules.append(
            {
                "id": str(raw.get("id", "")),
                "description": str(raw.get("description", "")),
                "when": raw.get("when", {}) if isinstance(raw.get("when"), dict) else {},
                "then": raw.get("then", "deny"),
                "modification": raw.get("modification"),
                "escalation_target": raw.get("escalation_target"),
            }
        )
    return Policy.model_validate(
        {
            "id": str(row.id),
            "name": row.name,
            "version": str(row.version),
            "rules": clean_rules,
            "default_verdict": "deny",
        }
    )


def _block_on_injection(row: PolicyModel) -> bool:
    rules = row.rules if isinstance(row.rules, list) else []
    return any(isinstance(raw, dict) and raw.get("block_on_injection") is True for raw in rules)


class AuthorityStage:
    name = "authority"

    def __init__(
        self,
        session: AsyncSession,
        explanation_engine: ExplanationEngine | None = None,
    ) -> None:
        self._session = session
        self._explanation = explanation_engine or ExplanationEngine()

    async def execute(self, ctx: PipelineContext) -> StageResult:
        start = time.monotonic()
        try:
            if ctx.policy_id is None:
                ctx.decision = PolicyDecision(
                    verdict=Verdict.DENY,
                    rule_id=None,
                    policy_id="UNKNOWN",
                    policy_version="0",
                    reasoning="no policy configured for this project",
                    modification=None,
                    escalation_target=None,
                )
                ctx.explanation = self._explanation.explain_no_policy()
                return StageResult(
                    ok=True,
                    stage_name=self.name,
                    duration_ms=(time.monotonic() - start) * 1000,
                    data={"verdict": ctx.decision.verdict.value, "no_policy": True},
                )

            row = await self._session.get(PolicyModel, UUID(ctx.policy_id))
            if row is None or row.deleted_at is not None:
                ctx.decision = PolicyDecision(
                    verdict=Verdict.DENY,
                    rule_id=None,
                    policy_id=ctx.policy_id,
                    policy_version=ctx.policy_version or "0",
                    reasoning="policy disappeared between strategy and authority",
                    modification=None,
                    escalation_target=None,
                )
                ctx.explanation = self._explanation.explain_no_policy()
                return StageResult(
                    ok=True,
                    stage_name=self.name,
                    duration_ms=(time.monotonic() - start) * 1000,
                    data={"verdict": ctx.decision.verdict.value, "policy_missing": True},
                )

            policy = _coerce_policy(row)
            decision = evaluate(policy, ctx.action)

            if ctx.injection_matches and _block_on_injection(row):
                decision = PolicyDecision(
                    verdict=Verdict.DENY,
                    rule_id=decision.rule_id,
                    policy_id=decision.policy_id,
                    policy_version=decision.policy_version,
                    reasoning=(
                        "injection detected ("
                        + ",".join(sorted({m.category.value for m in ctx.injection_matches}))
                        + "); policy enforces block_on_injection"
                    ),
                    modification=None,
                    escalation_target=None,
                )

            ctx.decision = decision
            ctx.explanation = self._explanation.explain(decision, row)
            return StageResult(
                ok=True,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                data={"verdict": decision.verdict.value, "rule_id": decision.rule_id},
            )
        except Exception as exc:  # noqa: BLE001 - fail-closed by design
            return StageResult(
                ok=False,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                error=f"authority_failed: {type(exc).__name__}: {str(exc)[:200]}",
            )
