"""Stage 2 (Strategy): select the policy to apply + pin its version at request time.

Responsibility: DB lookup only. Never blocks or decides. Writes
``ctx.policy_id`` and ``ctx.policy_version``; Stage 3 (Authority) consumes them.

Selection rule:
  1. If the project has an ``is_active=True`` policy whose ``rules`` metadata
     names ``action.type`` in an ``action_types`` list, prefer that policy.
  2. Otherwise fall back to the most recently updated active policy for the
     project.
  3. No active policy -> ``ctx.policy_id = None``. Stage 3 will emit a default
     DENY ("no policy configured").

Version pinning: we store ``str(policy.version)`` at request time. Phase 2.85
(policy change accountability) will rely on this freeze point; Phase 2 needs
the primitive to work end-to-end.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.policy import Policy
from axiom.services.pipeline.protocols import PipelineContext, StageResult


def _rules_cover_action_type(rules: object, action_type: str) -> bool:
    if not isinstance(rules, list):
        return False
    for raw in rules:
        if not isinstance(raw, dict):
            continue
        when = raw.get("when")
        if not isinstance(when, dict):
            continue
        pred = when.get("type")
        if pred is None:
            continue
        if isinstance(pred, dict):
            op = pred.get("op")
            value = pred.get("value")
            if op in {"eq", None} and value == action_type:
                return True
            if op == "in" and isinstance(value, list) and action_type in value:
                return True
        elif pred == action_type:
            return True
    return False


class StrategyStage:
    name = "strategy"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: PipelineContext) -> StageResult:
        start = time.monotonic()
        try:
            rows = await self._session.scalars(
                select(Policy)
                .where(
                    Policy.project_id == ctx.project_id,
                    Policy.is_active.is_(True),
                    Policy.deleted_at.is_(None),
                )
                .order_by(Policy.updated_at.desc())
            )
            candidates = list(rows)
        except Exception as exc:  # noqa: BLE001 - surface DB errors as fail-closed StageResult
            return StageResult(
                ok=False,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                error=f"policy_lookup_failed: {type(exc).__name__}",
            )

        action_type = str(ctx.action.get("type", ""))
        chosen: Policy | None = None
        for candidate in candidates:
            if action_type and _rules_cover_action_type(candidate.rules, action_type):
                chosen = candidate
                break
        if chosen is None and candidates:
            chosen = candidates[0]

        if chosen is not None:
            ctx.policy_id = str(chosen.id)
            ctx.policy_version = str(chosen.version)

        return StageResult(
            ok=True,
            stage_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
            data={
                "policy_id": ctx.policy_id,
                "policy_version": ctx.policy_version,
                "candidates": len(candidates),
            },
        )
