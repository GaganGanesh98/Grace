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
from axiom.schemas.policy import PolicyCreate, PolicyOut, PolicySearchResult, PolicyUpdate
from axiom.services import policies as policies_service
from axiom.services.events import schedule_policy_activated

router = APIRouter()


@router.get("/{project_id}/policies", response_model=ListEnvelope[PolicyOut])
async def list_policies(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ListEnvelope[PolicyOut]:
    params = clamp_page_params(page, per_page)
    offset = (params.page - 1) * params.per_page
    rows, total = await policies_service.list_policies(
        db, project_id=project_id, offset=offset, limit=params.per_page
    )
    meta = PaginationMeta(
        **pagination_meta(total=total, page=params.page, per_page=params.per_page),
    )
    return ListEnvelope(
        data=[PolicyOut.model_validate(r) for r in rows],
        meta=meta,
    )


@router.post(
    "/{project_id}/policies",
    response_model=DataEnvelope[PolicyOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_policy(
    project_id: UUID,
    body: PolicyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[PolicyOut]:
    policy = await policies_service.create_policy(
        db,
        project_id=project_id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        pack=body.pack,
        rules=list(body.rules),
        created_by_user_id=user.id,
    )
    return DataEnvelope(data=PolicyOut.model_validate(policy))


@router.get(
    "/{project_id}/policies/search",
    response_model=DataEnvelope[list[PolicySearchResult]],
)
async def search_policies(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
    q: Annotated[str, Query(min_length=1, description="Free-text query (e.g. an agent action)")],
    k: Annotated[int, Query(ge=1, le=50)] = 5,
) -> DataEnvelope[list[PolicySearchResult]]:
    """Semantically match active policies against a free-text query via pgvector
    cosine similarity. Declared before ``/{policy_id}`` so "search" is not parsed
    as a policy UUID."""
    matches = await policies_service.search_policies(
        db, project_id=project_id, query_text=q, k=k
    )
    return DataEnvelope(
        data=[
            PolicySearchResult(policy=PolicyOut.model_validate(policy), similarity=score)
            for policy, score in matches
        ]
    )


@router.get("/{project_id}/policies/{policy_id}", response_model=DataEnvelope[PolicyOut])
async def get_policy(
    project_id: UUID,
    policy_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.MEMBER))],
) -> DataEnvelope[PolicyOut]:
    policy = await policies_service.get_policy(db, project_id=project_id, policy_id=policy_id)
    return DataEnvelope(data=PolicyOut.model_validate(policy))


@router.patch("/{project_id}/policies/{policy_id}", response_model=DataEnvelope[PolicyOut])
async def patch_policy(
    project_id: UUID,
    policy_id: UUID,
    body: PolicyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[PolicyOut]:
    policy = await policies_service.get_policy(db, project_id=project_id, policy_id=policy_id)
    new_policy = await policies_service.update_policy_new_version(
        db,
        policy,
        name=body.name,
        description=body.description,
        pack=body.pack,
        rules=list(body.rules) if body.rules is not None else None,
        is_active=body.is_active,
        created_by_user_id=user.id,
    )
    if new_policy.is_active:
        await db.commit()
        schedule_policy_activated(
            new_policy.project_id,
            policy_id=new_policy.id,
            name=new_policy.name,
        )
    return DataEnvelope(data=PolicyOut.model_validate(new_policy))


@router.delete("/{project_id}/policies/{policy_id}", response_model=DataEnvelope[dict[str, str]])
async def delete_policy(
    project_id: UUID,
    policy_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _member: Annotated[ProjectMember, Depends(RequireProjectRole(MemberRole.ADMIN))],
) -> DataEnvelope[dict[str, str]]:
    policy = await policies_service.get_policy(db, project_id=project_id, policy_id=policy_id)
    await policies_service.soft_delete_policy(db, policy)
    return DataEnvelope(data={"status": "ok"})
