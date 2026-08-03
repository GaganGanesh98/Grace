"""Phase 2.5 governance engine — /v1/governance/* (does not replace legacy /v1/govern)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import (
    require_api_key,
    require_api_key_or_current_user,
    resolve_api_key_or_current_user,
)
from axiom.middleware.rate_limit import api_key_limit_key, limiter
from axiom.models.governance import (
    GovernanceChain,
    GovernanceIntent,
    GovernanceReceipt,
    GovernanceVerdict,
)
from axiom.models.user import User
from axiom.schemas.governance import (
    ActiveGovernancePolicyResponse,
    EngineReceiptResponse,
    GovernanceEngineVerifyResponse,
    GovernRequest,
    GovernResponse,
    ReportRequest,
    ReportResponse,
    VerifyGovernanceByReceiptIdRequest,
    VerifyReceiptRequest,
)
from axiom.services import projects as projects_service
from axiom.services.api_key import APIKeyContext
from axiom.services.escalation import schedule_escalation
from axiom.services.events import schedule_approval_created, schedule_receipt_sealed
from axiom.services.governance.chain import (
    ChainValidationError,
    auto_close_stale_chains,
    get_or_create_chain,
    update_chain_stats,
)
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import describe_active_governance_policy, evaluate_policy
from axiom.services.governance.receipt import create_pending_receipt, seal_receipt
from axiom.services.governance.receipt_duration import compute_receipt_duration_ms
from axiom.services.governance.verdict import render_verdict
from axiom.services.governance.verification import (
    verify_execution,
    verify_receipt_independent,
    verify_sealed_governance_receipt_from_db,
)
from axiom.services.receipt.keys import get_signing_keys

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get(
    "/policies/active",
    response_model=ActiveGovernancePolicyResponse,
    status_code=status.HTTP_200_OK,
)
async def get_active_governance_policy(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
) -> ActiveGovernancePolicyResponse:
    """Return the active governance YAML policy for the resolved project (no receipts required)."""

    project = await projects_service.get_project(db, api_ctx.project_id)
    settings = project.settings if isinstance(project.settings, dict) else {}
    payload = describe_active_governance_policy(settings)
    return ActiveGovernancePolicyResponse.model_validate(payload)


def _mask_verdict(intent: GovernanceIntent, raw: str) -> str:
    if intent.mode == "shadow":
        return "allow"
    return raw


def _intent_dict(intent: GovernanceIntent) -> dict[str, Any]:
    return {
        "id": str(intent.id),
        "project_id": str(intent.project_id),
        "agent_id": intent.agent_id,
        "action_type": intent.action_type,
        "target": intent.target,
        "parameters": intent.parameters,
        "risk_declared": intent.risk_declared,
        "mode": intent.mode,
        "metadata": intent.extra_metadata,
        "created_at": intent.created_at.isoformat(),
    }


def _verdict_dict(verdict: GovernanceVerdict) -> dict[str, Any]:
    return {
        "id": str(verdict.id),
        "verdict": verdict.verdict,
        "reason": verdict.reason,
        "policy_version": verdict.policy_version,
        "rules_evaluated": verdict.rules_evaluated,
        "risk_assessed": verdict.risk_assessed,
        "context": verdict.context,
        "created_at": verdict.created_at.isoformat(),
    }


async def _receipt_to_response(
    db: AsyncSession,
    receipt: GovernanceReceipt,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
) -> EngineReceiptResponse:
    proof = receipt.merkle_proof if isinstance(receipt.merkle_proof, dict) else {}
    path = proof.get("path") if isinstance(proof.get("path"), list) else []
    depth = len(path)
    merkle: dict[str, Any] = {
        "leaf": receipt.receipt_hash.hex() if receipt.receipt_hash else "",
        "root": receipt.merkle_root.hex() if receipt.merkle_root else "",
        "depth": depth,
        "leaf_index": proof.get("leaf_index"),
        "tree_size": proof.get("tree_size"),
        "path": path,
    }
    signatures = {
        "ed25519": base64.b64encode(receipt.ed25519_sig).decode("ascii")
        if receipt.ed25519_sig
        else "",
        "ml_dsa_65": base64.b64encode(receipt.ml_dsa_sig).decode("ascii")
        if receipt.ml_dsa_sig
        else "",
        "key_id": receipt.key_id or "",
    }
    verification = {
        "status": receipt.verification or "",
        "mismatches": receipt.mismatches or [],
    }
    execution = receipt.execution_data
    signer_public: dict[str, str] | None = None
    if receipt.status == "sealed":
        keys = get_signing_keys()
        signer_public = {
            "ed25519_public_pem": keys.ed25519_public,
            "ml_dsa_public_b64": base64.b64encode(keys.ml_dsa_public).decode("ascii"),
        }
    approved_by_email: str | None = None
    if receipt.approved_by_user_id is not None:
        approver = await db.get(User, receipt.approved_by_user_id)
        if approver is not None:
            approved_by_email = approver.email
    return EngineReceiptResponse(
        id=str(receipt.id),
        intent=_intent_dict(intent),
        verdict=_verdict_dict(verdict),
        execution=execution,
        verification=verification,
        signatures=signatures,
        merkle=merkle,
        policy_version=verdict.policy_version,
        sealed_at=receipt.sealed_at,
        status=receipt.status,
        signer_public=signer_public,
        approval_status=receipt.approval_status,
        approved_by=approved_by_email,
        approved_at=receipt.approved_at,
        approval_reason=receipt.approval_reason,
        approval_expires_at=receipt.approval_expires_at,
        duration_ms=compute_receipt_duration_ms(receipt),
    )


@router.post("/govern", response_model=GovernResponse, status_code=status.HTTP_200_OK)
@limiter.limit("100/minute", key_func=api_key_limit_key)
async def governance_govern(
    request: Request,
    body: GovernRequest,
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GovernResponse:
    _ = request
    await auto_close_stale_chains(db, api_ctx.project_id)
    try:
        chain = await get_or_create_chain(
            db,
            api_ctx.project_id,
            body.agent_id,
            body.workflow,
            body.chain_id,
        )
    except ChainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Invalid chain",
        ) from None

    intent = await declare_intent(
        db,
        api_ctx.project_id,
        body,
        chain_id=chain.id if chain else None,
    )
    context = await enrich_context(db, intent)
    policy_result = evaluate_policy(intent, context)
    verdict = await render_verdict(db, intent, policy_result, context)
    receipt = await create_pending_receipt(db, intent=intent, verdict=verdict)
    if verdict.verdict == "hold" and intent.mode != "shadow":
        receipt.approval_status = "pending"
        receipt.approval_expires_at = datetime.now(UTC) + timedelta(minutes=30)
    if chain is not None:
        await update_chain_stats(db, chain, verdict.verdict, None)
    await db.commit()
    if (
        verdict.verdict == "hold"
        and intent.mode != "shadow"
        and receipt.approval_expires_at is not None
    ):
        schedule_approval_created(
            api_ctx.project_id,
            receipt_id=receipt.id,
            expires_at=receipt.approval_expires_at,
        )
        # Additive: notify the n8n escalation flow (no-op unless ESCALATION_ENABLED).
        schedule_escalation(api_ctx.project_id, receipt.id)

    masked = _mask_verdict(intent, verdict.verdict)
    reason = None if intent.mode == "shadow" else verdict.reason
    if intent.mode == "shadow" and verdict.verdict != "allow":
        reason = f"Shadow mode: real verdict would be {verdict.verdict}" + (
            f" ({verdict.reason})" if verdict.reason else ""
        )

    logger.info(
        "governance.engine.govern",
        receipt_id=str(receipt.id),
        project_id=str(api_ctx.project_id),
        raw_verdict=verdict.verdict,
        response_verdict=masked,
    )

    appr_status = None
    appr_expires = None
    if verdict.verdict == "hold" and intent.mode != "shadow":
        appr_status = "pending"
        appr_expires = receipt.approval_expires_at

    return GovernResponse(
        receipt_id=str(receipt.id),
        verdict=masked,
        reason=reason,
        policy_version=verdict.policy_version,
        risk_assessed=verdict.risk_assessed,
        mode=intent.mode,
        chain_id=str(chain.id) if chain else None,
        approval_status=appr_status,
        approval_expires_at=appr_expires,
    )


@router.post("/report", response_model=ReportResponse, status_code=status.HTTP_200_OK)
@limiter.limit("100/minute", key_func=api_key_limit_key)
async def governance_report(
    request: Request,
    body: ReportRequest,
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    _ = request
    try:
        rid = UUID(body.receipt_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid receipt_id",
        ) from exc

    receipt = await db.get(GovernanceReceipt, rid)
    if receipt is None or receipt.project_id != api_ctx.project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    if receipt.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receipt is not pending")

    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    executed_at = body.executed_at
    if executed_at is None:
        executed_at = datetime.now(UTC)

    vres = verify_execution(intent, dict(body.outcome))

    try:
        receipt = await seal_receipt(
            db,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=dict(body.outcome),
            executed_at=executed_at,
            verification_result=vres,
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Receipt sealing failed",
        ) from None

    if intent.chain_id is not None:
        ch = await db.get(GovernanceChain, intent.chain_id)
        if ch is not None and ch.status == "active" and receipt.verification is not None:
            await update_chain_stats(db, ch, None, receipt.verification)

    await db.commit()
    schedule_receipt_sealed(
        api_ctx.project_id,
        receipt_id=receipt.id,
        verdict_raw=verdict.verdict,
        agent_id=str(intent.agent_id),
    )

    proof = receipt.merkle_proof if isinstance(receipt.merkle_proof, dict) else {}
    path = proof.get("path") if isinstance(proof.get("path"), list) else []
    merkle = {
        "leaf": receipt.receipt_hash.hex() if receipt.receipt_hash else "",
        "root": receipt.merkle_root.hex() if receipt.merkle_root else "",
        "depth": len(path),
    }

    return ReportResponse(
        receipt_id=str(receipt.id),
        status=receipt.status,
        verification=receipt.verification or "",
        mismatches=list(receipt.mismatches or []),
        signatures={
            "ed25519": receipt.ed25519_sig is not None,
            "ml_dsa_65": receipt.ml_dsa_sig is not None,
        },
        merkle=merkle,
    )


@router.get(
    "/receipts/{receipt_id}",
    response_model=EngineReceiptResponse,
    status_code=status.HTTP_200_OK,
)
async def get_governance_receipt(
    receipt_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    share_token: Annotated[str | None, Query(alias="share_token")] = None,
    project_id: Annotated[
        UUID | None,
        Query(description="JWT: required when the user belongs to multiple projects."),
    ] = None,
) -> EngineReceiptResponse:
    receipt = await db.get(GovernanceReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    allowed = False
    if share_token and intent.extra_metadata.get("public_share_token") == share_token:
        allowed = True
    if not allowed:
        api_ctx = await resolve_api_key_or_current_user(db, request, project_id)
        if receipt.project_id != api_ctx.project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    return await _receipt_to_response(db, receipt, intent, verdict)


@router.post(
    "/verify",
    response_model=GovernanceEngineVerifyResponse,
    status_code=status.HTTP_200_OK,
)
async def governance_verify_independent(
    request: Request,
    body: Annotated[
        VerifyGovernanceByReceiptIdRequest | VerifyReceiptRequest,
        Body(),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Annotated[
        UUID | None,
        Query(description="JWT: required when the user belongs to multiple projects."),
    ] = None,
) -> GovernanceEngineVerifyResponse:
    if isinstance(body, VerifyGovernanceByReceiptIdRequest):
        api_ctx = await resolve_api_key_or_current_user(db, request, project_id)
        try:
            rid = UUID(body.receipt_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid receipt_id",
            ) from exc
        receipt = await db.get(GovernanceReceipt, rid)
        if receipt is None or receipt.project_id != api_ctx.project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
        if receipt.status != "sealed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Receipt is not sealed",
            )
        intent = await db.get(GovernanceIntent, receipt.intent_id)
        verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
        if intent is None or verdict is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
        return verify_sealed_governance_receipt_from_db(receipt, intent, verdict)
    return verify_receipt_independent(body)
