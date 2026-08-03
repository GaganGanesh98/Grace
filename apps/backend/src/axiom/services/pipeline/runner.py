"""PipelineRunner — orchestrates the six stages with fail-closed semantics.

Invariants the runner enforces (NOT THE STAGES):
  1. Every call to ``run()`` produces a ``PipelineContext`` with a populated
     ``ctx.decision``. Silent drops are impossible.
  2. If a stage other than ``evidence`` or ``receipt`` fails (raises or returns
     ``ok=False``), the runner forces ``ctx.decision`` to DENY with a
     diagnostic ``reasoning`` and STILL executes Evidence + Receipt so the
     event is signed, logged, and Merkle-appended.
  3. If Evidence or Receipt fails, the runner stops (there's no point
     re-running Receipt on a Receipt failure) and the returned context's
     ``receipt_id`` is ``None``; the router surfaces HTTP 500 in that case
     (this is an operational failure, not a governance one).
  4. Every stage result (ok or not) is appended to ``ctx.stage_results`` in
     order, so the Evidence stage can include them in the signed payload.

Exactly six stages are required. Ordering must be Intent, Strategy, Authority,
Dispatch, Evidence, Receipt. The runner validates the sequence at construction.
"""

from __future__ import annotations

import time

import structlog

from axiom.services.pipeline.protocols import (
    PipelineContext,
    Stage,
    StageResult,
)
from axiom.services.policy.evaluator import PolicyDecision, Verdict

logger = structlog.get_logger(__name__)

_EXPECTED_ORDER: tuple[str, ...] = (
    "intent",
    "strategy",
    "authority",
    "dispatch",
    "evidence",
    "receipt",
)

_NON_FATAL_SHORT_CIRCUIT = {"intent", "strategy", "authority", "dispatch"}


class PipelineRunner:
    def __init__(self, stages: tuple[Stage, ...]) -> None:
        if len(stages) != 6:
            msg = f"Expected 6 stages, got {len(stages)}"
            raise ValueError(msg)
        names = tuple(s.name for s in stages)
        if names != _EXPECTED_ORDER:
            msg = f"Stage order must be {_EXPECTED_ORDER}, got {names}"
            raise ValueError(msg)
        self._stages = stages

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        short_circuited = False
        for stage in self._stages:
            # Once a pre-evidence stage has failed we skip intent/strategy/authority/dispatch
            # and jump straight to Evidence + Receipt so the fail-closed DENY still gets signed.
            if short_circuited and stage.name in _NON_FATAL_SHORT_CIRCUIT:
                continue

            result = await self._run_stage(stage, ctx)
            ctx.stage_results.append(result)

            if not result.ok and stage.name in _NON_FATAL_SHORT_CIRCUIT:
                self._force_deny(ctx, result)
                short_circuited = True
                continue

            if not result.ok and stage.name == "evidence":
                logger.error(
                    "pipeline.evidence_failed",
                    correlation_id=ctx.correlation_id,
                    error=result.error,
                )
                return ctx

            if not result.ok and stage.name == "receipt":
                logger.error(
                    "pipeline.receipt_failed",
                    correlation_id=ctx.correlation_id,
                    error=result.error,
                )
                return ctx
        return ctx

    async def _run_stage(self, stage: Stage, ctx: PipelineContext) -> StageResult:
        start = time.monotonic()
        try:
            return await stage.execute(ctx)
        except Exception as exc:  # noqa: BLE001 — fail-closed by design, logged + converted
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "pipeline.stage_exception",
                stage=stage.name,
                correlation_id=ctx.correlation_id,
                exc_info=True,
            )
            return StageResult(
                ok=False,
                stage_name=stage.name,
                duration_ms=duration_ms,
                error=f"{type(exc).__name__}: {str(exc)[:200]}",
            )

    @staticmethod
    def _force_deny(ctx: PipelineContext, result: StageResult) -> None:
        """Short-circuit: override the decision to DENY so Evidence+Receipt still sign it."""
        ctx.decision = PolicyDecision(
            verdict=Verdict.DENY,
            rule_id=None,
            policy_id=ctx.policy_id or "UNKNOWN",
            policy_version=ctx.policy_version or "0",
            reasoning=f"pipeline stage error: {result.stage_name}: {result.error}",
            modification=None,
            escalation_target=None,
        )
        ctx.explanation = (
            "Action denied because the governance pipeline encountered an error. "
            "Per fail-closed policy, ambiguous requests are never approved. "
            f"Stage reporting: {result.stage_name}."
        )
        ctx.dispatched = False
