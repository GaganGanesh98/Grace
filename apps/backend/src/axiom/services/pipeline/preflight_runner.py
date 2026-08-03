"""PreflightRunner — runs first 3 stages (Intent, Strategy, Authority) only.

Does NOT call Stages 4-6 (Dispatch, Evidence, Receipt). Does NOT produce a Receipt.
Does NOT write to DB. Fail-closed on any stage error — returns ctx with
decision.verdict = DENY and clear reasoning.

This runner is INTENTIONALLY distinct from PipelineRunner (Phase 2). They share the
Stage protocol from protocols.py but have different semantics:
- PipelineRunner: 6 stages, emits signed receipt, fail-closed to DENY with receipt
- PreflightRunner: 3 stages, NO receipt, fail-closed to DENY prediction only
"""

from __future__ import annotations

import time
from typing import Final

import structlog

from axiom.services.pipeline.protocols import (
    PipelineContext,
    Stage,
    StageResult,
)
from axiom.services.policy.evaluator import PolicyDecision, Verdict

logger = structlog.get_logger(__name__)

# Allowed stage names — PreflightRunner MUST reject anything else at init
_ALLOWED_STAGE_NAMES: Final = frozenset({"intent", "strategy", "authority"})


class PreflightRunner:
    """Runs the first 3 stages of the governance pipeline for prediction only.

    Instantiate with exactly 3 stages whose .name is in {"intent", "strategy", "authority"}.
    ValueError on any other count or name.

    This constraint is enforced at init time to make it structurally impossible to
    construct a PreflightRunner that accidentally emits a receipt.
    """

    def __init__(self, stages: tuple[Stage, Stage, Stage]) -> None:
        if len(stages) != 3:
            raise ValueError(f"PreflightRunner requires exactly 3 stages, got {len(stages)}")
        names = tuple(stage.name for stage in stages)
        if set(names) != _ALLOWED_STAGE_NAMES:
            raise ValueError(
                f"PreflightRunner requires stages {sorted(_ALLOWED_STAGE_NAMES)}, got {names}"
            )
        if names != ("intent", "strategy", "authority"):
            raise ValueError(f"Stages must be in order (intent, strategy, authority), got {names}")
        self._stages = stages

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Execute stages 1-3 fail-closed. Never runs Dispatch/Evidence/Receipt."""
        for stage in self._stages:
            start = time.monotonic()
            try:
                result = await stage.execute(ctx)
            except Exception as exc:  # noqa: BLE001 — fail-closed by design, logged + converted
                duration_ms = (time.monotonic() - start) * 1000
                logger.error(
                    "preflight_stage_exception",
                    stage=stage.name,
                    correlation_id=ctx.correlation_id,
                    exc_info=True,
                )
                result = StageResult(
                    ok=False,
                    stage_name=stage.name,
                    duration_ms=duration_ms,
                    error=f"{type(exc).__name__}: {str(exc)[:200]}",
                )
            ctx.stage_results.append(result)

            if not result.ok:
                # Short-circuit: force DENY prediction, stop here (no receipt generation)
                ctx.decision = PolicyDecision(
                    verdict=Verdict.DENY,
                    rule_id=None,
                    policy_id=ctx.policy_id or "UNKNOWN",
                    policy_version=ctx.policy_version or "0.0.0",
                    reasoning=f"preflight stage error: {result.stage_name}: {result.error}",
                    modification=None,
                    escalation_target=None,
                )
                ctx.explanation = (
                    "Pre-flight encountered an error. "
                    "Action would be denied per fail-closed policy."
                )
                return ctx

        # All 3 stages OK — ctx.decision is populated by Authority stage
        return ctx
