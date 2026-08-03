"""Governance workflow chains — /v1/chains/*."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import require_api_key_or_current_user
from axiom.middleware.rate_limit import api_key_limit_key, limiter
from axiom.models.governance import GovernanceChain
from axiom.schemas.governance import ChainCloseRequest, ChainListResponse, ChainSummary
from axiom.services.api_key import APIKeyContext
from axiom.services.governance.chain import (
    chain_compliance_rate,
    close_chain,
    get_chain,
    list_chains,
    list_receipt_summaries_for_chain,
    verify_chain_signatures,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


async def _to_chain_summary(db_chain: GovernanceChain, records: list[dict]) -> ChainSummary:
    sig = None
    if db_chain.status in ("sealed", "auto_closed") and db_chain.chain_hash is not None:
        sig = verify_chain_signatures(db_chain)
    return ChainSummary(
        id=str(db_chain.id),
        workflow_name=db_chain.workflow_name,
        agent_id=db_chain.agent_id,
        status=db_chain.status,
        total_actions=db_chain.total_actions,
        authorized=db_chain.authorized,
        held=db_chain.held,
        denied=db_chain.denied,
        compliant=db_chain.compliant,
        non_compliant=db_chain.non_compliant,
        compliance_rate=chain_compliance_rate(db_chain),
        chain_signature=sig,
        started_at=db_chain.started_at,
        closed_at=db_chain.closed_at,
        sealed_at=db_chain.sealed_at,
        records=records,
    )


@router.get("", response_model=ChainListResponse, status_code=status.HTTP_200_OK)
@limiter.limit("100/minute", key_func=api_key_limit_key)
async def list_governance_chains(
    request: Request,
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> ChainListResponse:
    _ = request
    rows, total = await list_chains(
        db,
        api_ctx.project_id,
        page=page,
        per_page=per_page,
        status=status_filter,
    )
    summaries: list[ChainSummary] = []
    for row in rows:
        recs = await list_receipt_summaries_for_chain(db, row.id)
        summaries.append(await _to_chain_summary(row, recs))
    return ChainListResponse(
        chains=summaries,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{chain_id}",
    response_model=ChainSummary,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("100/minute", key_func=api_key_limit_key)
async def get_governance_chain(
    request: Request,
    chain_id: UUID,
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChainSummary:
    _ = request
    ch = await get_chain(db, chain_id)
    if ch is None or ch.project_id != api_ctx.project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")
    records = await list_receipt_summaries_for_chain(db, chain_id)
    return await _to_chain_summary(ch, records)


@router.post(
    "/{chain_id}/close",
    response_model=ChainSummary,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("100/minute", key_func=api_key_limit_key)
async def close_governance_chain(
    request: Request,
    chain_id: UUID,
    _body: Annotated[ChainCloseRequest, Body()],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChainSummary:
    _ = request, _body
    ch = await get_chain(db, chain_id)
    if ch is None or ch.project_id != api_ctx.project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")
    if ch.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chain is not active or already sealed",
        )
    await close_chain(db, ch, auto_closed=False)
    await db.commit()
    records = await list_receipt_summaries_for_chain(db, chain_id)
    refreshed = await get_chain(db, chain_id)
    if refreshed is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chain state unavailable after close",
        )
    logger.info("governance.chain.close_api", chain_id=str(chain_id))
    return await _to_chain_summary(refreshed, records)
