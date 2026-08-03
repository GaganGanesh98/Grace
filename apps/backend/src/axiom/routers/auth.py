from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.db import get_db
from axiom.deps import get_current_user
from axiom.middleware.rate_limit import limiter
from axiom.models.user import User
from axiom.schemas.auth import (
    GoogleAuthorizeResponse,
    GoogleCallbackRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserPublic,
)
from axiom.schemas.common import DataEnvelope
from axiom.services import auth as auth_service
from axiom.services import google_oauth as google_oauth_service

router = APIRouter()


@router.post("/signup", response_model=DataEnvelope[TokenPair], status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def signup(
    request: Request,
    body: SignupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataEnvelope[TokenPair]:
    _user, access, refresh = await auth_service.signup(
        db,
        email=str(body.email),
        password=body.password,
        full_name=body.full_name,
    )
    return DataEnvelope(data=TokenPair(access_token=access, refresh_token=refresh))


@router.post("/login", response_model=DataEnvelope[TokenPair])
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataEnvelope[TokenPair]:
    _user, access, refresh = await auth_service.login(
        db,
        email=str(body.email),
        password=body.password,
    )
    return DataEnvelope(data=TokenPair(access_token=access, refresh_token=refresh))


@router.post("/refresh", response_model=DataEnvelope[TokenPair])
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataEnvelope[TokenPair]:
    _user, access, new_refresh = await auth_service.refresh_tokens(
        db,
        refresh_token=body.refresh_token,
    )
    return DataEnvelope(data=TokenPair(access_token=access, refresh_token=new_refresh))


@router.post("/logout", response_model=DataEnvelope[dict[str, str]])
async def logout(
    body: LogoutRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> DataEnvelope[dict[str, str]]:
    await auth_service.logout(refresh_token=body.refresh_token)
    return DataEnvelope(data={"status": "ok"})


@router.get("/google/authorize", response_model=DataEnvelope[GoogleAuthorizeResponse])
async def google_authorize() -> DataEnvelope[GoogleAuthorizeResponse]:
    url, state = await google_oauth_service.build_authorize_url()
    return DataEnvelope(data=GoogleAuthorizeResponse(url=url, state=state))


@router.post("/google/callback", response_model=DataEnvelope[TokenPair])
@limiter.limit("10/minute")
async def google_callback(
    request: Request,
    body: GoogleCallbackRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataEnvelope[TokenPair]:
    profile = await google_oauth_service.exchange_code(code=body.code, state=body.state or None)
    sub = str(profile.get("sub", ""))
    email = str(profile.get("email", ""))
    if not sub or not email:
        raise errors.InvalidCredentialsError("Google profile missing required fields.")
    name = profile.get("name")
    picture = profile.get("picture")
    user, access, refresh = await auth_service.ensure_google_user(
        db,
        email=email,
        google_sub=sub,
        full_name=str(name) if name is not None else None,
        avatar_url=str(picture) if picture is not None else None,
    )
    _ = user
    return DataEnvelope(data=TokenPair(access_token=access, refresh_token=refresh))


@router.get("/me", response_model=DataEnvelope[UserPublic])
async def me(user: Annotated[User, Depends(get_current_user)]) -> DataEnvelope[UserPublic]:
    return DataEnvelope(data=UserPublic.model_validate(user))
