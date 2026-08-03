"""User vault (encrypted credentials)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import get_current_user
from axiom.models.user import User
from axiom.schemas.vault import (
    VaultDetectBody,
    VaultDetectResponse,
    VaultKeyCreate,
    VaultKeyCreatedResponse,
    VaultKeyDeletedResponse,
    VaultKeyListItem,
    VaultKeyPatch,
)
from axiom.services import vault as vault_service

router = APIRouter()


@router.get("", response_model=list[VaultKeyListItem])
async def list_vault_keys(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    kind: str | None = Query(
        default=None, description="Filter: llm, tool, or custom"
    ),
) -> list[VaultKeyListItem]:
    rows = await vault_service.list_keys(db, user.id, kind=kind)
    return [
        VaultKeyListItem(
            id=r.id,
            kind=r.kind,
            service=r.service,
            name=r.name,
            key_prefix=r.key_prefix,
            key_suffix=r.key_suffix,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post(
    "",
    response_model=VaultKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vault_key(
    body: VaultKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> VaultKeyCreatedResponse:
    row, d_kind, d_service = await vault_service.create_vault_key(
        db,
        user.id,
        body.name,
        body.raw_key,
        kind_override=body.kind_override,
        service_override=body.service_override,
    )
    return VaultKeyCreatedResponse(
        id=row.id,
        kind=row.kind,
        service=row.service,
        name=row.name,
        key_prefix=row.key_prefix,
        key_suffix=row.key_suffix,
        detected_kind=d_kind,
        detected_service=d_service,
        created_at=row.created_at,
    )


@router.post("/detect", response_model=VaultDetectResponse)
async def detect_vault_credential(
    body: VaultDetectBody,
    _user: Annotated[User, Depends(get_current_user)],
) -> VaultDetectResponse:
    kind, service = vault_service.detect_credential_kind_and_service(body.raw_key)
    return VaultDetectResponse(kind=kind, service=service)


@router.get("/{key_id}", response_model=VaultKeyListItem)
async def get_vault_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> VaultKeyListItem:
    r = await vault_service.get_vault_key(db, user.id, key_id)
    return VaultKeyListItem(
        id=r.id,
        kind=r.kind,
        service=r.service,
        name=r.name,
        key_prefix=r.key_prefix,
        key_suffix=r.key_suffix,
        is_active=r.is_active,
        created_at=r.created_at,
    )


@router.patch(
    "/{key_id}",
    response_model=VaultKeyListItem,
)
async def patch_vault_key(
    key_id: UUID,
    body: VaultKeyPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> VaultKeyListItem:
    if body.name is None and body.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide name and/or is_active",
        )
    d = await vault_service.update_vault_key(
        db, user.id, key_id, name=body.name, is_active=body.is_active
    )
    return VaultKeyListItem(
        id=d.id,
        kind=d.kind,
        service=d.service,
        name=d.name,
        key_prefix=d.key_prefix,
        key_suffix=d.key_suffix,
        is_active=d.is_active,
        created_at=d.created_at,
    )


# NOTE: DELETE returns 200 + JSON (not 204) for BFF compatibility.
@router.delete("/{key_id}", response_model=VaultKeyDeletedResponse)
async def delete_vault_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> VaultKeyDeletedResponse:
    deleted_id = await vault_service.delete_key(db, user.id, key_id)
    return VaultKeyDeletedResponse(deleted=True, id=deleted_id)


@router.post(
    "/{key_id}/deactivate",
    response_model=VaultKeyListItem,
)
async def post_deactivate_vault_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> VaultKeyListItem:
    d = await vault_service.deactivate_vault_key(db, user.id, key_id)
    return VaultKeyListItem(
        id=d.id,
        kind=d.kind,
        service=d.service,
        name=d.name,
        key_prefix=d.key_prefix,
        key_suffix=d.key_suffix,
        is_active=d.is_active,
        created_at=d.created_at,
    )
