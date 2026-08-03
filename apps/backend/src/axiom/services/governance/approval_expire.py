"""Expire pending human approvals and seal receipts (deny)."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.services.governance.chain import adjust_chain_after_hold_resolution
from axiom.services.governance.hold_resolution import seal_pending_after_hold_decision, utcnow

logger = structlog.get_logger(__name__)


async def expire_due_hold_receipts(
    db: AsyncSession,
) -> list[tuple[GovernanceReceipt, GovernanceIntent, UUID, str]]:
    """Mark pending approvals as expired (verdict deny), seal, adjust chain stats.

    Returns rows for firing ``approval.resolved`` + ``receipt.sealed`` **after** the session commits.
    """
    now = utcnow()
    rows = (
        await db.scalars(
            select(GovernanceReceipt).where(
                GovernanceReceipt.approval_status == "pending",
                GovernanceReceipt.approval_expires_at.is_not(None),
                GovernanceReceipt.approval_expires_at < now,
                GovernanceReceipt.status == "pending",
            )
        )
    ).all()

    out: list[tuple[GovernanceReceipt, GovernanceIntent, UUID, str]] = []
    for receipt in rows:
        verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
        intent = await db.get(GovernanceIntent, receipt.intent_id)
        if verdict is None or intent is None:
            continue
        verdict.verdict = "deny"
        receipt.approval_status = "expired"
        await seal_pending_after_hold_decision(
            db,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
        )
        await adjust_chain_after_hold_resolution(
            db,
            intent.chain_id,
            final_verdict="deny",
        )
        out.append((receipt, intent, receipt.project_id, str(verdict.verdict)))
        logger.info(
            "governance.approval.expired",
            receipt_id=str(receipt.id),
            project_id=str(receipt.project_id),
        )
    return out
