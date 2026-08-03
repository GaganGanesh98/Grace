"""Phase 7.2 — Command Center receipt detail + agent run artifact download."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import require_api_key_or_current_user, resolve_api_key_or_current_user
from axiom.models.agent_run import AgentRun
from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.schemas.command_center import (
    CryptoHealthOut,
    PolicyBreakdownOut,
    PostureOut,
    TsaStatusOut,
)
from axiom.schemas.common import DataEnvelope
from axiom.services.api_key import APIKeyContext
from axiom.services.command_center.aggregates import AggregatesService
from axiom.services.command_center.receipt_detail import build_command_center_receipt_detail
from axiom.workers.tools.file_write import artifact_path_for_run

router = APIRouter()


@router.get(
    "/command-center/posture",
    response_model=DataEnvelope[PostureOut],
)
async def command_center_posture(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    window: str = Query("24h", description="Rolling window, e.g. 24h, 1h, 7d."),
) -> DataEnvelope[PostureOut]:
    svc = AggregatesService(db)
    out = await svc.get_posture(api_ctx.project_id, window=window)
    return DataEnvelope(data=out)


@router.get(
    "/command-center/crypto-health",
    response_model=DataEnvelope[CryptoHealthOut],
)
async def command_center_crypto_health(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
) -> DataEnvelope[CryptoHealthOut]:
    svc = AggregatesService(db)
    out = await svc.get_crypto_health(api_ctx.project_id)
    return DataEnvelope(data=out)


@router.get(
    "/command-center/policy-breakdown",
    response_model=DataEnvelope[PolicyBreakdownOut],
)
async def command_center_policy_breakdown(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    window: str = Query("24h", description="Rolling window, e.g. 24h, 1h, 7d."),
) -> DataEnvelope[PolicyBreakdownOut]:
    svc = AggregatesService(db)
    out = await svc.get_policy_breakdown(api_ctx.project_id, window=window)
    return DataEnvelope(data=out)


@router.get(
    "/command-center/tsa-status",
    response_model=DataEnvelope[TsaStatusOut],
)
async def command_center_tsa_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
) -> DataEnvelope[TsaStatusOut]:
    svc = AggregatesService(db)
    out = await svc.get_tsa_status(api_ctx.project_id)
    return DataEnvelope(data=out)


@router.get("/receipts/{receipt_id}")
async def get_command_center_receipt(
    receipt_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Annotated[
        UUID | None,
        Query(description="JWT: required when the user belongs to multiple projects."),
    ] = None,
) -> dict:
    """Full receipt payload for the dashboard drawer (Phase 7.2)."""
    receipt = await db.get(GovernanceReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "receipt_not_found",
                "receipt_id": str(receipt_id),
                "endpoint": "GET /v1/receipts/{receipt_id}",
                "message": "Receipt not found in the governance ledger.",
            },
        )

    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "receipt_incomplete",
                "receipt_id": str(receipt_id),
                "endpoint": "GET /v1/receipts/{receipt_id}",
                "message": "Receipt metadata incomplete.",
            },
        )

    api_ctx = await resolve_api_key_or_current_user(db, request, project_id)
    if receipt.project_id != api_ctx.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this receipt in the active workspace.",
        )

    return build_command_center_receipt_detail(receipt=receipt, intent=intent, verdict=verdict)


@router.get("/agent-runs/{run_id}/artifacts/{filename}")
async def download_agent_run_artifact(
    run_id: UUID,
    filename: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Annotated[
        UUID | None,
        Query(description="JWT: required when the user belongs to multiple projects."),
    ] = None,
) -> Response:
    """Stream a run artifact file with Content-Disposition (Phase 7.2)."""
    api_ctx = await resolve_api_key_or_current_user(db, request, project_id)
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    if run.project_id != api_ctx.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this agent run or artifact.",
        )

    path = artifact_path_for_run(run_id, filename)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact file not found.",
        )

    body = path.read_bytes()
    ct = "application/octet-stream"
    safe = quote(filename)
    headers = {
        "Content-Disposition": f'attachment; filename="{safe}"; filename*=UTF-8\'\'{safe}',
        "Content-Type": ct,
        "Content-Length": str(len(body)),
    }
    return Response(content=body, media_type=ct, headers=headers)
