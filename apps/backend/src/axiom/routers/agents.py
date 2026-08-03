from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.pagination import clamp_page_params, pagination_meta
from axiom.db import get_db
from axiom.deps import RequireProjectRole, get_current_user
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.user import User
from axiom.schemas.agent import AgentCreate, AgentOut, AgentUpdate
from axiom.schemas.common import DataEnvelope, ListEnvelope, PaginationMeta
from axiom.services import agents as agents_service

router = APIRouter()


@router.get("/{project_id}/agents", response_model=ListEnvelope[AgentOut])
async def list_agents(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ListEnvelope[AgentOut]:
    params = clamp_page_params(page, per_page)
    offset = (params.page - 1) * params.per_page
    rows, total = await agents_service.list_agents(
        db, project_id=project_id, offset=offset, limit=params.per_page
    )
    meta = PaginationMeta(
        **pagination_meta(total=total, page=params.page, per_page=params.per_page),
    )
    return ListEnvelope(
        data=[AgentOut.model_validate(r) for r in rows],
        meta=meta,
    )


@router.post(
    "/{project_id}/agents",
    response_model=DataEnvelope[AgentOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    project_id: UUID,
    body: AgentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[AgentOut]:
    agent = await agents_service.create_agent(
        db,
        project_id=project_id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        agent_type=body.agent_type,
        default_mode=body.default_mode,
        metadata=body.metadata_,
        created_by_user_id=user.id,
    )
    return DataEnvelope(data=AgentOut.model_validate(agent))


@router.get("/{project_id}/agents/{agent_id}", response_model=DataEnvelope[AgentOut])
async def get_agent(
    project_id: UUID,
    agent_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
) -> DataEnvelope[AgentOut]:
    agent = await agents_service.get_agent(db, project_id=project_id, agent_id=agent_id)
    return DataEnvelope(data=AgentOut.model_validate(agent))


@router.patch("/{project_id}/agents/{agent_id}", response_model=DataEnvelope[AgentOut])
async def patch_agent(
    project_id: UUID,
    agent_id: UUID,
    body: AgentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[AgentOut]:
    agent = await agents_service.get_agent(db, project_id=project_id, agent_id=agent_id)
    updated = await agents_service.update_agent(
        db,
        agent,
        name=body.name,
        description=body.description,
        agent_type=body.agent_type,
        default_mode=body.default_mode,
        metadata=body.metadata_,
        is_active=body.is_active,
    )
    return DataEnvelope(data=AgentOut.model_validate(updated))


@router.delete("/{project_id}/agents/{agent_id}", response_model=DataEnvelope[dict[str, str]])
async def delete_agent(
    project_id: UUID,
    agent_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[dict[str, str]]:
    agent = await agents_service.get_agent(db, project_id=project_id, agent_id=agent_id)
    await agents_service.soft_delete_agent(db, agent)
    return DataEnvelope(data={"status": "ok"})
