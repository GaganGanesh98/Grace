"""Phase 6.5 — /v1/agent-definitions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.pagination import clamp_page_params, pagination_meta
from axiom.db import get_db
from axiom.deps import created_by_user_id, require_api_key_or_current_user
from axiom.schemas.agent_definitions import AgentDefinitionCreate, AgentDefinitionOut, AgentDefinitionPatch
from axiom.schemas.common import DataEnvelope, ListEnvelope, PaginationMeta
from axiom.services.agent_definitions import AgentDefinitionService
from axiom.services.api_key import APIKeyContext

router = APIRouter()


@router.get("/agent-definitions", response_model=ListEnvelope[AgentDefinitionOut])
async def list_agent_definitions(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ListEnvelope[AgentDefinitionOut]:
    params = clamp_page_params(page, per_page)
    offset = (params.page - 1) * params.per_page
    svc = AgentDefinitionService(db)
    rows, total = await svc.list(
        project_id=api_ctx.project_id, offset=offset, limit=params.per_page
    )
    meta = PaginationMeta(
        **pagination_meta(total=total, page=params.page, per_page=params.per_page),
    )
    return ListEnvelope(
        data=[AgentDefinitionOut.model_validate(r) for r in rows],
        meta=meta,
    )


@router.post(
    "/agent-definitions",
    response_model=DataEnvelope[AgentDefinitionOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_definition(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    actor_user_id: Annotated[UUID, Depends(created_by_user_id)],
    body: AgentDefinitionCreate,
) -> DataEnvelope[AgentDefinitionOut]:
    svc = AgentDefinitionService(db)
    row = await svc.create(
        project_id=api_ctx.project_id,
        name=body.name,
        model=body.model,
        vault_key_id=body.vault_key_id,
        created_by_user_id=actor_user_id,
        description=body.description,
        system_prompt=body.system_prompt,
        tools_config=body.tools_config,
        max_iterations=body.max_iterations,
        max_tokens_per_run=body.max_tokens_per_run,
    )
    return DataEnvelope(data=AgentDefinitionOut.model_validate(row))


@router.get(
    "/agent-definitions/{definition_id}",
    response_model=DataEnvelope[AgentDefinitionOut],
)
async def get_agent_definition(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    definition_id: UUID,
) -> DataEnvelope[AgentDefinitionOut]:
    svc = AgentDefinitionService(db)
    row = await svc.get(project_id=api_ctx.project_id, definition_id=definition_id)
    return DataEnvelope(data=AgentDefinitionOut.model_validate(row))


@router.patch(
    "/agent-definitions/{definition_id}",
    response_model=DataEnvelope[AgentDefinitionOut],
)
async def patch_agent_definition(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
    definition_id: UUID,
    body: AgentDefinitionPatch,
) -> DataEnvelope[AgentDefinitionOut]:
    if body.is_archived is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No mutable fields provided.",
        )
    svc = AgentDefinitionService(db)
    row = await svc.get(project_id=api_ctx.project_id, definition_id=definition_id)
    if body.is_archived is True:
        row = await svc.archive(row)
    elif body.is_archived is False:
        row.is_archived = False
    return DataEnvelope(data=AgentDefinitionOut.model_validate(row))
