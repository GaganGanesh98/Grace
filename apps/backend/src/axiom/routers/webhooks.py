"""Inbound webhooks. Currently: the n8n escalation-result callback.

Authenticated by HMAC over the raw body (shared secret N8N_CALLBACK_SECRET),
not by user/api-key auth — n8n is a machine caller. The callback resolves a
pending governance receipt by reusing the existing hold-resolution path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.db import get_db
from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.schemas.escalation import (
    EscalationCallbackRequest,
    EscalationCallbackResponse,
    EscalationDecision,
)
from axiom.services.escalation.signing import SIGNATURE_HEADER, verify_signature
from axiom.services.events import schedule_approval_resolved, schedule_receipt_sealed
from axiom.services.governance.chain import adjust_chain_after_hold_resolution
from axiom.services.governance.hold_resolution import seal_pending_after_hold_decision

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/n8n/escalation-result",
    response_model=EscalationCallbackResponse,
    status_code=status.HTTP_200_OK,
)
async def n8n_escalation_result(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    signature: Annotated[str | None, Header(alias=SIGNATURE_HEADER)] = None,
) -> EscalationCallbackResponse:
    """n8n reports its decision for an escalated action.

    Verifies ``X-Axiom-Signature`` (HMAC-SHA256 of the raw body) before doing
    anything, then resolves the pending receipt: approved -> allow, rejected ->
    deny (both sealed via the existing hold-resolution path), escalated_to_human
    -> left pending for the human approval flow.
    """
    settings = get_settings()
    secret = settings.n8n_callback_secret
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Escalation callback secret is not configured",
        )

    raw = await request.body()
    if not verify_signature(secret.get_secret_value(), raw, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing signature",
        )

    try:
        body = EscalationCallbackRequest.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid callback body"
        ) from exc

    receipt = await db.get(GovernanceReceipt, body.receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    if receipt.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Receipt is not awaiting approval"
        )

    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    now = datetime.now(UTC)
    if receipt.approval_expires_at is not None and receipt.approval_expires_at < now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Approval window expired")

    reason = f"n8n: {body.reason}" if body.reason else "n8n auto-decision"

    # n8n couldn't auto-decide: leave the receipt pending for a human to resolve
    # via the existing approvals endpoints.
    if body.decision is EscalationDecision.ESCALATED_TO_HUMAN:
        receipt.approval_reason = reason
        await db.commit()
        logger.info("escalation.callback_escalated_to_human", receipt_id=str(receipt.id))
        return EscalationCallbackResponse(receipt_id=receipt.id, approval_status="pending")

    if body.decision is EscalationDecision.APPROVED:
        verdict.verdict = "allow"
        receipt.approval_status = "approved"
        final_verdict = "allow"
    else:  # REJECTED
        verdict.verdict = "deny"
        receipt.approval_status = "rejected"
        final_verdict = "deny"
    receipt.approved_at = now
    receipt.approval_reason = reason

    try:
        await seal_pending_after_hold_decision(db, receipt=receipt, intent=intent, verdict=verdict)
        await adjust_chain_after_hold_resolution(db, intent.chain_id, final_verdict=final_verdict)
        await db.commit()
    except RuntimeError as exc:
        await db.rollback()
        logger.exception("escalation.callback_seal_failed", receipt_id=str(receipt.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Receipt sealing failed"
        ) from exc

    schedule_approval_resolved(
        receipt.project_id, receipt_id=receipt.id, resolution=receipt.approval_status
    )
    schedule_receipt_sealed(
        receipt.project_id,
        receipt_id=receipt.id,
        verdict_raw=verdict.verdict,
        agent_id=str(intent.agent_id),
    )
    logger.info(
        "escalation.callback_resolved",
        receipt_id=str(receipt.id),
        decision=body.decision.value,
    )
    return EscalationCallbackResponse(
        receipt_id=receipt.id, approval_status=receipt.approval_status
    )
