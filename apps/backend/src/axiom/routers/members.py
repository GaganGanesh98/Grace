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
from axiom.schemas.member import MemberInvite, MemberListItemOut, MemberOut, MemberRoleUpdate
from axiom.services import members as members_service
from axiom.services import projects as projects_service

router = APIRouter()


@router.get("/{project_id}/members", response_model=ListEnvelope[MemberListItemOut])
async def list_members(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ListEnvelope[MemberListItemOut]:
    params = clamp_page_params(page, per_page)
    offset = (params.page - 1) * params.per_page
    rows, total = await members_service.list_members(
        db, project_id=project_id, offset=offset, limit=params.per_page
    )
    meta = PaginationMeta(
        **pagination_meta(total=total, page=params.page, per_page=params.per_page),
    )
    out: list[MemberListItemOut] = []
    for r in rows:
        u = r.user
        out.append(
            MemberListItemOut(
                id=r.id,
                project_id=r.project_id,
                user_id=r.user_id,
                role=r.role,
                invited_by_user_id=r.invited_by_user_id,
                joined_at=r.joined_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
                user_email=str(u.email) if u is not None else "",
                full_name=u.full_name if u is not None else None,
            )
        )
    return ListEnvelope(data=out, meta=meta)


@router.post(
    "/{project_id}/members",
    response_model=DataEnvelope[MemberOut],
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    project_id: UUID,
    body: MemberInvite,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[MemberOut]:
    project = await projects_service.get_project(db, project_id)
    member = await members_service.invite_member(
        db,
        project=project,
        email=str(body.email),
        role=body.role,
        invited_by=user,
    )
    return DataEnvelope(data=MemberOut.model_validate(member))


@router.patch("/{project_id}/members/{member_id}", response_model=DataEnvelope[MemberOut])
async def patch_member_role(
    project_id: UUID,
    member_id: UUID,
    body: MemberRoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    actor_membership: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[MemberOut]:
    member = await members_service.get_member_by_id(db, project_id=project_id, member_id=member_id)
    updated = await members_service.update_member_role(
        db,
        member=member,
        new_role=body.role,
        actor=user,
        actor_membership=actor_membership,
    )
    return DataEnvelope(data=MemberOut.model_validate(updated))


@router.delete("/{project_id}/members/{member_id}", response_model=DataEnvelope[dict[str, str]])
async def delete_member(
    project_id: UUID,
    member_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    actor_membership: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[dict[str, str]]:
    member = await members_service.get_member_by_id(db, project_id=project_id, member_id=member_id)
    await members_service.remove_member(
        db,
        member=member,
        actor=user,
        actor_membership=actor_membership,
    )
    return DataEnvelope(data={"status": "ok"})
