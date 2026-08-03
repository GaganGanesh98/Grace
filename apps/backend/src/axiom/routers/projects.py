from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.pagination import clamp_page_params, pagination_meta
from axiom.db import get_db
from axiom.deps import RequireProjectRole, get_current_user
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.user import User
from axiom.schemas.common import DataEnvelope, ListEnvelope, PaginationMeta
from axiom.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from axiom.services import projects as projects_service

router = APIRouter()


@router.get("", response_model=ListEnvelope[ProjectOut])
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ListEnvelope[ProjectOut]:
    params = clamp_page_params(page, per_page)
    offset = (params.page - 1) * params.per_page
    rows, total = await projects_service.list_projects_for_user(
        db,
        user_id=user.id,
        offset=offset,
        limit=params.per_page,
    )
    meta = PaginationMeta(
        **pagination_meta(total=total, page=params.page, per_page=params.per_page),
    )
    return ListEnvelope(
        data=[ProjectOut.model_validate(r) for r in rows],
        meta=meta,
    )


@router.post("", response_model=DataEnvelope[ProjectOut], status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DataEnvelope[ProjectOut]:
    project = await projects_service.create_project(
        db,
        owner=user,
        name=body.name,
        description=body.description,
        slug=body.slug,
    )
    return DataEnvelope(data=ProjectOut.model_validate(project))


@router.get("/{project_id}", response_model=DataEnvelope[ProjectOut])
async def get_project(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
) -> DataEnvelope[ProjectOut]:
    project = await projects_service.get_project(db, project_id)
    return DataEnvelope(data=ProjectOut.model_validate(project))


@router.patch("/{project_id}", response_model=DataEnvelope[ProjectOut])
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[ProjectOut]:
    project = await projects_service.get_project(db, project_id)
    updated = await projects_service.update_project(
        db,
        project,
        name=body.name,
        description=body.description,
    )
    return DataEnvelope(data=ProjectOut.model_validate(updated))


@router.delete("/{project_id}", response_model=DataEnvelope[dict[str, str]])
async def delete_project(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.OWNER))],
) -> DataEnvelope[dict[str, str]]:
    project = await projects_service.get_project(db, project_id)
    await projects_service.soft_delete_project(db, project)
    return DataEnvelope(data={"status": "ok"})
