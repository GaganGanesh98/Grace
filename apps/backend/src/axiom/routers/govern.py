"""POST /v1/govern — core governance execution endpoint.

MATCH-GAAS. 100 req/min per API key. Body cap 100 KB.
"""

from __future__ import annotations

import base64
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.db import get_db
from axiom.deps import require_api_key
from axiom.middleware.rate_limit import api_key_limit_key, limiter
from axiom.schemas.governance import GovernanceRequest, GovernanceResponse
from axiom.services.api_key import APIKeyContext
from axiom.services.receipt.service import ReceiptService

_MAX_BODY_BYTES = 100 * 1024

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "/govern",
    response_model=GovernanceResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("100/minute", key_func=api_key_limit_key)
async def govern(
    request: Request,
    body: GovernanceRequest,
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GovernanceResponse:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request body exceeds 100 KB cap for /v1/govern",
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header",
            ) from exc

    correlation_id = str(getattr(request.state, "correlation_id", None) or uuid.uuid4())

    service = ReceiptService(db)
    ctx = await service.process(
        project_id=api_ctx.project_id,
        agent_id=body.agent_id,
        api_key_id=api_ctx.api_key_id,
        correlation_id=correlation_id,
        action=body.action,
        mode=body.mode,
    )

    if (
        ctx.receipt_id is None
        or ctx.signature is None
        or ctx.merkle_root is None
        or ctx.merkle_tree_size is None
        or ctx.merkle_leaf_index is None
        or ctx.execution_id is None
        or ctx.decision is None
    ):
        logger.error(
            "govern.receipt_incomplete",
            correlation_id=correlation_id,
            project_id=str(api_ctx.project_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Receipt generation failed; no evidence was recorded. Please retry.",
        )

    logger.info(
        "govern.executed",
        correlation_id=correlation_id,
        project_id=str(api_ctx.project_id),
        agent_id=str(body.agent_id),
        api_key_id=str(api_ctx.api_key_id),
        verdict=ctx.decision.verdict.value,
        policy_id=ctx.decision.policy_id,
        mode=ctx.mode.value,
        leaf_index=ctx.merkle_leaf_index,
        dispatched=ctx.dispatched,
    )

    settings = get_settings()
    verify_url = f"{settings.verify_base_url.rstrip('/')}/v1/verify/{ctx.receipt_id}"

    return GovernanceResponse(
        receipt_id=ctx.receipt_id,
        execution_id=ctx.execution_id,
        verdict=ctx.decision.verdict,
        reasoning=ctx.decision.reasoning,
        explanation=ctx.explanation or "",
        modification=ctx.decision.modification,
        escalation_target=ctx.decision.escalation_target,
        merkle_leaf_index=ctx.merkle_leaf_index,
        merkle_tree_size=ctx.merkle_tree_size,
        merkle_root=base64.b64encode(ctx.merkle_root).decode("ascii"),
        verify_url=verify_url,
        dispatched=ctx.dispatched,
        correlation_id=correlation_id,
        algorithm=ctx.signature.algorithm,
        signed_at=ctx.requested_at,
    )
