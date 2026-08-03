"""Stage 4 (Dispatch): decide whether the caller is ALLOWED to proceed.

AXIOM never executes the agent's action. We only record our verdict; the
caller uses ``dispatched`` to decide what to do next.

Mode semantics:
  * SHADOW  -> ``dispatched=False`` always. Records a receipt for the verdict
               but never signals "you may proceed" (the caller is observing
               AXIOM, not obeying it yet).
  * ENFORCE -> APPROVE / MODIFY -> ``dispatched=True``.
               DENY    / ESCALATE -> ``dispatched=False``.

MODIFY deserves a note: Phase 2 does NOT rewrite the action in flight. The
modification is recorded on the receipt and returned in the response; the
caller is expected to apply it and (optionally) re-submit. This keeps the
engine deterministic and makes the receipt faithful to what was decided.
"""

from __future__ import annotations

import time

from axiom.services.pipeline.protocols import PipelineContext, PipelineMode, StageResult
from axiom.services.policy.evaluator import Verdict


class DispatchStage:
    name = "dispatch"

    async def execute(self, ctx: PipelineContext) -> StageResult:
        start = time.monotonic()
        decision = ctx.decision
        if decision is None:
            return StageResult(
                ok=False,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                error="dispatch_without_decision",
            )

        if ctx.mode is PipelineMode.SHADOW:
            ctx.dispatched = False
        else:
            ctx.dispatched = decision.verdict in {Verdict.APPROVE, Verdict.MODIFY}

        return StageResult(
            ok=True,
            stage_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
            data={
                "mode": ctx.mode.value,
                "verdict": decision.verdict.value,
                "dispatched": ctx.dispatched,
            },
        )
