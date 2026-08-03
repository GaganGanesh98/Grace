"""Phase 6.5 — /v1/agent-runs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.pagination import clamp_page_params, pagination_meta
from axiom.db import get_db
from axiom.deps import require_api_key_or_current_user
from axiom.models.agent_definition import AgentDefinition
from axiom.schemas.agent_runs import AgentRunCreate, AgentRunOut, AgentRunWsTokenResponse
from axiom.schemas.common import DataEnvelope, ListEnvelope, PaginationMeta
from axiom.services.agent_runs import AgentRunService
from axiom.services.api_key import APIKeyContext

router = APIRouter()


@router.get("/agent-runs", response_model=ListEnvelope[AgentRunOut])
async def list_agent_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(
        default=None,
        description="Filter by run status: pending, running, succeeded, failed, cancelled",
    ),
    q: str | None = Query(
        default=None,
        description="Search run id, goal (input.goal), or agent definition name (substring, case-insensitive).",
    ),
) -> ListEnvelope[AgentRunOut]:
    params = clamp_page_params(page, per_page)
    offset = (params.page - 1) * params.per_page
    svc = AgentRunService(db)
    rows, total = await svc.list(
        project_id=api_ctx.project_id,
        offset=offset,
        limit=params.per_page,
        status=status,
        q=q,
    )
    meta = PaginationMeta(
        **pagination_meta(total=total, page=params.page, per_page=params.per_page),
    )
    return ListEnvelope(
        data=[AgentRunOut.model_validate(r) for r in rows],
        meta=meta,
    )


@router.post(
    "/agent-runs",
    response_model=DataEnvelope[AgentRunOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_run(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    body: AgentRunCreate,
) -> DataEnvelope[AgentRunOut]:
    exists = await db.scalar(
        select(AgentDefinition.id).where(
            AgentDefinition.id == body.agent_definition_id,
            AgentDefinition.project_id == api_ctx.project_id,
            AgentDefinition.is_archived.is_(False),
        )
    )
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent definition not found for this project.",
        )
    svc = AgentRunService(db)
    run, _token, _cid = await svc.create(
        project_id=api_ctx.project_id,
        agent_definition_id=body.agent_definition_id,
        input_payload=body.input,
    )
    return DataEnvelope(data=AgentRunOut.model_validate(run))


@router.get(
    "/agent-runs/{run_id}",
    response_model=DataEnvelope[AgentRunOut],
)
async def get_agent_run(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    run_id: UUID,
) -> DataEnvelope[AgentRunOut]:
    svc = AgentRunService(db)
    run = await svc.get(project_id=api_ctx.project_id, run_id=run_id)
    return DataEnvelope(data=AgentRunOut.model_validate(run))


@router.post(
    "/agent-runs/{run_id}/cancel",
    response_model=DataEnvelope[AgentRunOut],
)
async def cancel_agent_run(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    run_id: UUID,
) -> DataEnvelope[AgentRunOut]:
    svc = AgentRunService(db)
    updated = await svc.cancel(project_id=api_ctx.project_id, run_id=run_id)
    return DataEnvelope(data=AgentRunOut.model_validate(updated))


@router.post(
    "/agent-runs/{run_id}/ws-token",
    response_model=DataEnvelope[AgentRunWsTokenResponse],
)
async def agent_run_ws_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    run_id: UUID,
) -> DataEnvelope[AgentRunWsTokenResponse]:
    svc = AgentRunService(db)
    run = await svc.get(project_id=api_ctx.project_id, run_id=run_id)
    token = svc.mint_ws_token(run)
    return DataEnvelope(
        data=AgentRunWsTokenResponse(token=token, expires_in_seconds=300),
    )
