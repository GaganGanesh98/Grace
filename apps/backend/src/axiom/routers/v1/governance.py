"""Phase 2.5 governance engine — /v1/governance/* (does not replace legacy /v1/govern)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
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
from axiom.services.events import schedule_receipt_sealed
from axiom.services.governance.chain import update_chain_stats
from axiom.services.governance.execute import ChainRejectedError, execute_governed_action
from axiom.services.governance.policy import describe_active_governance_policy
from axiom.services.governance.receipt import seal_receipt
from axiom.services.governance.receipt_duration import compute_receipt_duration_ms
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
    proof: dict[str, Any] = receipt.merkle_proof if isinstance(receipt.merkle_proof, dict) else {}
    raw_path = proof.get("path")
    path: list[Any] = raw_path if isinstance(raw_path, list) else []
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
    try:
        outcome = await execute_governed_action(db, project_id=api_ctx.project_id, request=body)
    except ChainRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Invalid chain",
        ) from None

    return GovernResponse(
        receipt_id=str(outcome.receipt_id),
        verdict=outcome.response_verdict,
        reason=outcome.reason,
        policy_version=outcome.verdict.policy_version,
        risk_assessed=outcome.verdict.risk_assessed,
        mode=outcome.intent.mode,
        chain_id=str(outcome.chain.id) if outcome.chain else None,
        approval_status=outcome.approval_status,
        approval_expires_at=outcome.approval_expires_at,
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

    proof: dict[str, Any] = receipt.merkle_proof if isinstance(receipt.merkle_proof, dict) else {}
    raw_path = proof.get("path")
    path: list[Any] = raw_path if isinstance(raw_path, list) else []
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
