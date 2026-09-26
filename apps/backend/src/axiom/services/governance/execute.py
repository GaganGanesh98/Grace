"""The governed-action path, as a service (Phase 9.1).

This sequence — chain → intent → context → policy → verdict → pending receipt →
hold handling → post-commit dispatch — used to live inline in
``routers/v1/governance.py``. Phase 9.1 adds a second caller (the n8n webhook),
and a third is foreseeable (MCP), so it moves here: one implementation, one set
of hold semantics, one place where shadow masking is decided.

Contract 5 in ``.importlinter`` is the same reasoning applied to the MCP
surface — a delivery mechanism consumes services; it does not re-implement them.

Scheduling lives here rather than in the callers so that every surface gets
identical side effects. Both schedules happen strictly after the commit, per the
``services.events.schedule_*`` convention: fire-and-forget, never raising into
the request path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import (
    GovernanceChain,
    GovernanceIntent,
    GovernanceReceipt,
    GovernanceVerdict,
)
from axiom.schemas.governance import GovernRequest
from axiom.services.escalation import schedule_escalation
from axiom.services.events import schedule_approval_created
from axiom.services.governance.chain import (
    ChainValidationError,
    auto_close_stale_chains,
    get_or_create_chain,
    update_chain_stats,
)
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import evaluate_policy
from axiom.services.governance.receipt import create_pending_receipt
from axiom.services.governance.verdict import render_verdict

logger = structlog.get_logger(__name__)

#: How long a held action waits for a decision before the expiry sweep closes it.
HOLD_WINDOW = timedelta(minutes=30)


@dataclass(frozen=True)
class GovernedAction:
    """Outcome of one governed action, shaped for any delivery surface.

    ``response_verdict`` is the value a caller should return: in shadow mode the
    stored verdict stays truthful while the response reads ``allow``. Callers
    must not re-derive this — that divergence is exactly what this type prevents.
    """

    receipt: GovernanceReceipt
    intent: GovernanceIntent
    verdict: GovernanceVerdict
    chain: GovernanceChain | None
    response_verdict: str
    reason: str | None
    approval_status: str | None
    approval_expires_at: datetime | None

    @property
    def receipt_id(self) -> UUID:
        return self.receipt.id

    @property
    def is_held(self) -> bool:
        return self.approval_status == "pending"


class ChainRejectedError(Exception):
    """The requested chain is invalid or belongs to another project."""


def _mask_verdict(intent: GovernanceIntent, raw: str) -> str:
    """Shadow mode reports ``allow`` while the stored verdict stays truthful."""
    if intent.mode == "shadow":
        return "allow"
    return raw


def _response_reason(intent: GovernanceIntent, verdict: GovernanceVerdict) -> str | None:
    if intent.mode != "shadow":
        return verdict.reason
    if verdict.verdict == "allow":
        return None
    suffix = f" ({verdict.reason})" if verdict.reason else ""
    return f"Shadow mode: real verdict would be {verdict.verdict}{suffix}"


async def execute_governed_action(
    db: AsyncSession,
    *,
    project_id: UUID,
    request: GovernRequest,
) -> GovernedAction:
    """Evaluate one action against the project's policy and record a receipt.

    Commits, then schedules the approval + escalation side effects when the
    verdict is a hold. Raises :class:`ChainRejectedError` when ``chain_id`` does not
    resolve — callers map that to their own 4xx.
    """
    await auto_close_stale_chains(db, project_id)
    try:
        chain = await get_or_create_chain(
            db, project_id, request.agent_id, request.workflow, request.chain_id
        )
    except ChainValidationError as exc:
        raise ChainRejectedError(str(exc) or "Invalid chain") from None

    intent = await declare_intent(db, project_id, request, chain_id=chain.id if chain else None)
    context = await enrich_context(db, intent)
    policy_result = evaluate_policy(intent, context)
    verdict = await render_verdict(db, intent, policy_result, context)
    receipt = await create_pending_receipt(db, intent=intent, verdict=verdict)

    held = verdict.verdict == "hold" and intent.mode != "shadow"
    if held:
        receipt.approval_status = "pending"
        receipt.approval_expires_at = datetime.now(UTC) + HOLD_WINDOW
    if chain is not None:
        await update_chain_stats(db, chain, verdict.verdict, None)
    await db.commit()

    if held and receipt.approval_expires_at is not None:
        schedule_approval_created(
            project_id, receipt_id=receipt.id, expires_at=receipt.approval_expires_at
        )
        # Additive: notify the n8n escalation flow (no-op unless ESCALATION_ENABLED).
        schedule_escalation(project_id, receipt.id)

    logger.info(
        "governance.engine.govern",
        receipt_id=str(receipt.id),
        project_id=str(project_id),
        raw_verdict=verdict.verdict,
        response_verdict=_mask_verdict(intent, verdict.verdict),
    )

    return GovernedAction(
        receipt=receipt,
        intent=intent,
        verdict=verdict,
        chain=chain,
        response_verdict=_mask_verdict(intent, verdict.verdict),
        reason=_response_reason(intent, verdict),
        approval_status="pending" if held else None,
        approval_expires_at=receipt.approval_expires_at if held else None,
    )
