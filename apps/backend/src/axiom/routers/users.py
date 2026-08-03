from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import get_current_user
from axiom.models.user import User
from axiom.schemas.auth import UserPublic
from axiom.schemas.common import DataEnvelope
from axiom.schemas.user import UserPasswordUpdate, UserProfileUpdate
from axiom.services import users as users_service

router = APIRouter()


@router.patch("/me", response_model=DataEnvelope[UserPublic])
async def patch_me(
    body: UserProfileUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DataEnvelope[UserPublic]:
    updated = await users_service.update_profile(
        db,
        user,
        full_name=body.full_name,
        avatar_url=body.avatar_url,
    )
    return DataEnvelope(data=UserPublic.model_validate(updated))


@router.post("/me/password", response_model=DataEnvelope[dict[str, str]])
async def change_password(
    body: UserPasswordUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DataEnvelope[dict[str, str]]:
    await users_service.change_password(
        db,
        user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return DataEnvelope(data={"status": "ok"})
