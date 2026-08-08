"""Inbound webhooks for machine callers.

Two endpoints, both authenticated by HMAC over the raw body rather than by
user/api-key auth, because the caller is an orchestrator and not a person:

* ``/n8n/escalation-result`` — n8n reports its decision for an action Grace
  already held. Resolves an existing receipt.
* ``/n8n/govern-action`` — any n8n workflow asks Grace to govern an action it is
  about to take. Creates a receipt. Phase 9.1.

They use **different secrets** because they have different blast radii: the
callback can only resolve a receipt Grace already created, while govern-action
can originate one for any project.

Explicit non-goals for ``/n8n/govern-action`` (AP-1.8, "workflow orchestration
creep"): Grace does not schedule these calls, does not retain workflow state
beyond the idempotency key, does not retry on the workflow's behalf, and does
not model steps, branches, or resumption. n8n owns orchestration; Grace sits in
the governance call and answers one question about one action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

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
from axiom.schemas.governance import GovernRequest
from axiom.schemas.n8n_action import N8nGovernActionRequest, N8nGovernActionResponse
from axiom.services.escalation.signing import SIGNATURE_HEADER, verify_signature
from axiom.services.events import schedule_approval_resolved, schedule_receipt_sealed
from axiom.services.governance.chain import adjust_chain_after_hold_resolution
from axiom.services.governance.execute import ChainRejectedError, execute_governed_action
from axiom.services.governance.hold_resolution import seal_pending_after_hold_decision
from axiom.services.governance.idempotency import (
    ClaimState,
    claim_run,
    record_receipt,
    release_claim,
)

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


def _verify_url(receipt_id: UUID | str) -> str:
    base = get_settings().verify_base_url.rstrip("/")
    return f"{base}/v1/verify/{receipt_id}"


async def _replayed_response(db: AsyncSession, receipt_id: str) -> N8nGovernActionResponse:
    """Rebuild the original answer from the stored receipt.

    A replay must return what the first call returned — reading it back out of
    the database is the only way to guarantee that, and it also catches the case
    where the receipt was resolved (approved/rejected) between the two calls.
    """
    try:
        rid = UUID(receipt_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Idempotency record is corrupt",
        ) from exc

    receipt = await db.get(GovernanceReceipt, rid)
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt from a previous run no longer exists",
        )
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    intent = await db.get(GovernanceIntent, receipt.intent_id)
    if verdict is None or intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt from a previous run is incomplete",
        )

    masked = "allow" if intent.mode == "shadow" else verdict.verdict
    return N8nGovernActionResponse(
        receipt_id=str(receipt.id),
        verdict=masked,
        reason=None if intent.mode == "shadow" else verdict.reason,
        verify_url=_verify_url(receipt.id),
        corrected_parameters=None,
        replayed=True,
    )


@router.post(
    "/n8n/govern-action",
    response_model=N8nGovernActionResponse,
    status_code=status.HTTP_200_OK,
)
async def n8n_govern_action(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    signature: Annotated[str | None, Header(alias=SIGNATURE_HEADER)] = None,
) -> N8nGovernActionResponse:
    """Govern one action on behalf of an external workflow.

    The reusable entry point: any n8n (or Zapier, or Temporal) workflow that
    wants a governed action posts here and switches on the verdict. Every call
    produces a receipt, so a workflow's actions are as auditable as an agent's.

    Verifies ``X-Axiom-Signature`` over the raw body *before* parsing, then
    delegates to ``execute_governed_action`` — the same service the HTTP and MCP
    surfaces use, so a workflow cannot get a different answer than an agent would
    for the same action.
    """
    settings = get_settings()
    secret = settings.n8n_action_secret
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Governed-action webhook secret is not configured",
        )

    raw = await request.body()
    if not verify_signature(secret.get_secret_value(), raw, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing signature",
        )

    try:
        body = N8nGovernActionRequest.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid governed-action body",
        ) from exc

    ttl = settings.n8n_action_idempotency_ttl_seconds
    claim = await claim_run(body.workflow_id, body.workflow_run_id, ttl_seconds=ttl)
    if claim.state is ClaimState.REPLAY and claim.receipt_id:
        logger.info(
            "n8n.action.replayed",
            workflow_id=body.workflow_id,
            workflow_run_id=body.workflow_run_id,
            receipt_id=claim.receipt_id,
        )
        return await _replayed_response(db, claim.receipt_id)
    if claim.state is ClaimState.IN_FLIGHT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workflow run is already being governed; retry shortly",
        )

    # `advise` is the orchestrator-facing name for the engine's shadow mode:
    # evaluate and record, but always answer `allow` so the workflow proceeds.
    govern_request = GovernRequest(
        agent_id=body.agent_id,
        action_type=body.action_type,
        target=body.target,
        parameters=dict(body.parameters),
        risk=body.risk,
        mode="enforce" if body.mode == "enforce" else "shadow",
        metadata={
            "source": "n8n",
            "workflow_id": body.workflow_id,
            "workflow_run_id": body.workflow_run_id,
        },
        workflow=body.workflow_id,
    )

    # Any exit from here that is not a governed action must release the claim,
    # or the workflow is stranded until the TTL expires with no way to retry.
    # `finally` rather than a broad handler: it covers every failure mode without
    # swallowing any of them.
    governed = False
    try:
        outcome = await execute_governed_action(
            db, project_id=body.project_id, request=govern_request
        )
        governed = True
    except ChainRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc) or "Invalid chain"
        ) from None
    finally:
        if not governed:
            await release_claim(body.workflow_id, body.workflow_run_id)

    await record_receipt(
        body.workflow_id, body.workflow_run_id, str(outcome.receipt_id), ttl_seconds=ttl
    )

    logger.info(
        "n8n.action.governed",
        workflow_id=body.workflow_id,
        workflow_run_id=body.workflow_run_id,
        project_id=str(body.project_id),
        receipt_id=str(outcome.receipt_id),
        verdict=outcome.response_verdict,
    )

    return N8nGovernActionResponse(
        receipt_id=str(outcome.receipt_id),
        verdict=outcome.response_verdict,
        reason=outcome.reason,
        verify_url=_verify_url(outcome.receipt_id),
        corrected_parameters=None,
        replayed=False,
    )
