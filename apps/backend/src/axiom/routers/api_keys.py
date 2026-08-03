from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.pagination import clamp_page_params, pagination_meta
from axiom.db import get_db
from axiom.deps import RequireProjectRole, get_current_user
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.user import User
from axiom.schemas.api_key import ApiKeyCreate, ApiKeyCreatedOut, ApiKeyOut
from axiom.schemas.common import DataEnvelope, ListEnvelope, PaginationMeta
from axiom.services import api_keys as api_keys_service

router = APIRouter()


@router.get("/{project_id}/api-keys", response_model=ListEnvelope[ApiKeyOut])
async def list_api_keys(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ListEnvelope[ApiKeyOut]:
    params = clamp_page_params(page, per_page)
    offset = (params.page - 1) * params.per_page
    rows, total = await api_keys_service.list_api_keys(
        db, project_id=project_id, offset=offset, limit=params.per_page
    )
    meta = PaginationMeta(
        **pagination_meta(total=total, page=params.page, per_page=params.per_page),
    )
    return ListEnvelope(
        data=[ApiKeyOut.model_validate(r) for r in rows],
        meta=meta,
    )


@router.post(
    "/{project_id}/api-keys",
    response_model=DataEnvelope[ApiKeyCreatedOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    project_id: UUID,
    body: ApiKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[ApiKeyCreatedOut]:
    row, full = await api_keys_service.create_api_key(
        db,
        project_id=project_id,
        name=body.name,
        scopes=body.scopes,
        created_by_user_id=user.id,
        expires_at=body.expires_at,
    )
    base = ApiKeyOut.model_validate(row)
    created = ApiKeyCreatedOut(**base.model_dump(), full_key=full)
    return DataEnvelope(data=created)


@router.delete("/{project_id}/api-keys/{key_id}", response_model=DataEnvelope[dict[str, str]])
async def revoke_api_key(
    project_id: UUID,
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[dict[str, str]]:
    key = await api_keys_service.get_api_key(db, project_id=project_id, key_id=key_id)
    await api_keys_service.revoke_api_key(db, key)
    return DataEnvelope(data={"status": "ok"})
