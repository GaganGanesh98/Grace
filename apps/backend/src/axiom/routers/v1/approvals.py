"""Human approval workflow for held governance receipts (JWT, dashboard)."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import get_current_user
from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.models.user import User
from axiom.schemas.governance import (
    ApprovalRequest,
    ApprovalResponse,
    ExtendHoldResponse,
    PendingReceiptsResponse,
    PendingReceiptSummary,
)
from axiom.services import members as members_service
from axiom.services.events import schedule_approval_resolved, schedule_receipt_sealed
from axiom.services.governance.chain import adjust_chain_after_hold_resolution
from axiom.services.governance.hold_resolution import seal_pending_after_hold_decision, utcnow

router = APIRouter()
logger = structlog.get_logger(__name__)


async def _require_project_member(
    db: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
) -> None:
    m = await members_service.get_membership(db, project_id=project_id, user_id=user_id)
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this project",
        )


@router.post(
    "/receipts/{receipt_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_governance_receipt(
    receipt_id: UUID,
    body: ApprovalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ApprovalResponse:
    receipt = await db.get(GovernanceReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    await _require_project_member(db, project_id=receipt.project_id, user_id=user.id)

    if receipt.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receipt is not awaiting approval",
        )

    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    now = utcnow()
    if receipt.approval_expires_at is not None and receipt.approval_expires_at < now:
        verdict.verdict = "deny"
        receipt.approval_status = "expired"
        try:
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
            await db.commit()
            schedule_approval_resolved(
                receipt.project_id, receipt_id=receipt.id, resolution="expired"
            )
            schedule_receipt_sealed(
                receipt.project_id,
                receipt_id=receipt.id,
                verdict_raw=verdict.verdict,
                agent_id=str(intent.agent_id),
            )
        except RuntimeError:
            await db.rollback()
            logger.exception("governance.approve.expire_seal_failed", receipt_id=str(receipt_id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Receipt sealing failed",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Approval window expired",
        )

    verdict.verdict = "allow"
    receipt.approval_status = "approved"
    receipt.approved_by_user_id = user.id
    receipt.approved_at = now
    receipt.approval_reason = body.reason
    try:
        await seal_pending_after_hold_decision(
            db,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
        )
        await adjust_chain_after_hold_resolution(
            db,
            intent.chain_id,
            final_verdict="allow",
        )
        await db.commit()
        schedule_approval_resolved(
            receipt.project_id, receipt_id=receipt.id, resolution="approved"
        )
        schedule_receipt_sealed(
            receipt.project_id,
            receipt_id=receipt.id,
            verdict_raw=verdict.verdict,
            agent_id=str(intent.agent_id),
        )
    except RuntimeError:
        await db.rollback()
        logger.exception("governance.approve.seal_failed", receipt_id=str(receipt_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Receipt sealing failed",
        ) from None

    return ApprovalResponse(
        receipt_id=receipt.id,
        approval_status="approved",
        approved_by=user.email,
        approved_at=receipt.approved_at,
        verdict="allow",
        reason=verdict.reason,
    )


@router.post(
    "/receipts/{receipt_id}/reject",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
)
async def reject_governance_receipt(
    receipt_id: UUID,
    body: ApprovalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ApprovalResponse:
    receipt = await db.get(GovernanceReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    await _require_project_member(db, project_id=receipt.project_id, user_id=user.id)

    if receipt.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receipt is not awaiting approval",
        )

    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    now = utcnow()
    if receipt.approval_expires_at is not None and receipt.approval_expires_at < now:
        verdict.verdict = "deny"
        receipt.approval_status = "expired"
        try:
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
            await db.commit()
            schedule_approval_resolved(
                receipt.project_id, receipt_id=receipt.id, resolution="expired"
            )
            schedule_receipt_sealed(
                receipt.project_id,
                receipt_id=receipt.id,
                verdict_raw=verdict.verdict,
                agent_id=str(intent.agent_id),
            )
        except RuntimeError:
            await db.rollback()
            logger.exception("governance.reject.expire_seal_failed", receipt_id=str(receipt_id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Receipt sealing failed",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Approval window expired",
        )

    verdict.verdict = "deny"
    receipt.approval_status = "rejected"
    receipt.approved_by_user_id = user.id
    receipt.approved_at = now
    receipt.approval_reason = body.reason
    try:
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
        await db.commit()
        schedule_approval_resolved(
            receipt.project_id, receipt_id=receipt.id, resolution="rejected"
        )
        schedule_receipt_sealed(
            receipt.project_id,
            receipt_id=receipt.id,
            verdict_raw=verdict.verdict,
            agent_id=str(intent.agent_id),
        )
    except RuntimeError:
        await db.rollback()
        logger.exception("governance.reject.seal_failed", receipt_id=str(receipt_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Receipt sealing failed",
        ) from None

    return ApprovalResponse(
        receipt_id=receipt.id,
        approval_status="rejected",
        approved_by=user.email,
        approved_at=receipt.approved_at,
        verdict="deny",
        reason=verdict.reason,
    )


@router.post(
    "/receipts/{receipt_id}/extend-hold",
    response_model=ExtendHoldResponse,
    status_code=status.HTTP_200_OK,
)
async def extend_hold(
    receipt_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ExtendHoldResponse:
    receipt = await db.get(GovernanceReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    await _require_project_member(db, project_id=receipt.project_id, user_id=user.id)

    if receipt.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receipt is not awaiting approval",
        )

    now = utcnow()
    base = receipt.approval_expires_at or now
    if base < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Approval window already expired",
        )

    receipt.approval_expires_at = base + timedelta(minutes=30)
    receipt.updated_at = now
    await db.commit()
    return ExtendHoldResponse(approval_expires_at=receipt.approval_expires_at)


@router.get(
    "/receipts/pending",
    response_model=PendingReceiptsResponse,
    status_code=status.HTTP_200_OK,
)
async def list_pending_receipts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    project_id: Annotated[UUID, Query(..., description="Project scope")],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PendingReceiptsResponse:
    await _require_project_member(db, project_id=project_id, user_id=user.id)

    total = int(
        await db.scalar(
            select(func.count())
            .select_from(GovernanceReceipt)
            .where(
                GovernanceReceipt.project_id == project_id,
                GovernanceReceipt.approval_status == "pending",
            )
        )
        or 0
    )

    now = utcnow()
    res = await db.execute(
        select(GovernanceReceipt, GovernanceIntent, GovernanceVerdict)
        .join(GovernanceIntent, GovernanceReceipt.intent_id == GovernanceIntent.id)
        .join(GovernanceVerdict, GovernanceReceipt.verdict_id == GovernanceVerdict.id)
        .where(
            GovernanceReceipt.project_id == project_id,
            GovernanceReceipt.approval_status == "pending",
        )
        .order_by(GovernanceReceipt.approval_expires_at.asc())
        .limit(limit)
    )
    rows = res.all()

    summaries: list[PendingReceiptSummary] = []
    for receipt, intent, verdict in rows:
        exp = receipt.approval_expires_at or now
        remaining = max(0, int((exp - now).total_seconds()))
        summaries.append(
            PendingReceiptSummary(
                receipt_id=receipt.id,
                agent_id=intent.agent_id,
                action_type=intent.action_type,
                target=intent.target,
                risk=verdict.risk_assessed,
                reason=verdict.reason,
                created_at=receipt.created_at,
                approval_expires_at=exp,
                time_remaining_seconds=remaining,
            )
        )

    return PendingReceiptsResponse(receipts=summaries, total=total)
