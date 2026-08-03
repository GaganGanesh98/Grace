from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.core.security import decode_token
from axiom.db import get_db
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.user import User
from axiom.services import auth as auth_service
from axiom.services import members as members_service
from axiom.services import projects as projects_service
from axiom.services.api_key import APIKeyContext, verify_key

if TYPE_CHECKING:
    from axiom.services.preflight.service import PreflightService

security = HTTPBearer(auto_error=False)

# Placeholder api_key_id for JWT-backed dashboard sessions (not a row in api_keys).
_JWT_SESSION_API_KEY_ID = UUID("00000000-0000-4000-8000-000000000001")


async def resolve_api_key_or_current_user(
    db: AsyncSession,
    request: Request,
    project_id: UUID | None,
) -> APIKeyContext:
    """Resolve dashboard or SDK identity to ``APIKeyContext`` (same shape as ``require_api_key``).

    * ``Authorization: Bearer axm_*`` or ``X-Api-Key`` → verified API key (existing SDK path).
    * ``Authorization: Bearer <JWT>`` → session user; project from membership (see ``project_id``).
    """
    presented = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        presented = auth_header[7:].strip()
    if not presented:
        presented = request.headers.get("x-api-key", "").strip()
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    ctx = await verify_key(db, presented, required_scope="govern:write")
    if ctx is not None:
        return ctx

    if presented.startswith(("axm_live_", "axm_test_")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    try:
        payload = decode_token(presented)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    try:
        user_id = UUID(str(payload["sub"]))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
    try:
        user = await auth_service.get_user_by_id(db, user_id)
    except errors.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        ) from None

    rows, total = await projects_service.list_projects_for_user(
        db, user_id=user.id, offset=0, limit=500
    )
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No project access",
        )
    if total == 1:
        resolved_pid = rows[0].id
    else:
        if project_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="project_id query parameter required when user belongs to multiple projects",
            )
        membership = await members_service.get_membership(
            db, project_id=project_id, user_id=user.id
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access this project",
            )
        resolved_pid = project_id

    return APIKeyContext(
        api_key_id=_JWT_SESSION_API_KEY_ID,
        project_id=resolved_pid,
        created_by_user_id=user.id,
        scopes=("govern:write",),
        key_prefix="jwt_session",
    )


async def require_api_key_or_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Annotated[
        UUID | None,
        Query(description="Required for JWT auth when the user belongs to multiple projects."),
    ] = None,
) -> APIKeyContext:
    """Like ``require_api_key`` but also accepts a session JWT (dashboard / BFF)."""

    return await resolve_api_key_or_current_user(db, request, project_id)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    try:
        user_id = UUID(str(payload["sub"]))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
    try:
        return await auth_service.get_user_by_id(db, user_id)
    except errors.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        ) from None


def _rank(role: str) -> int:
    mapping = {"MEMBER": 1, "ADMIN": 2, "OWNER": 3}
    return mapping.get(role, 0)


async def project_member(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ProjectMember:
    membership = await members_service.get_membership(db, project_id=project_id, user_id=user.id)
    if membership is None:
        raise errors.ProjectNotFoundError("Project not found.")
    return membership


async def require_api_key(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIKeyContext:
    """Dependency for ``/v1/govern`` and ``/v1/disclose``.

    Accepts either ``Authorization: Bearer axm_<...>`` or ``X-Api-Key: axm_<...>``.
    Returns the bound ``APIKeyContext`` or raises 401.
    """

    presented = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        presented = auth_header[7:].strip()
    if not presented:
        presented = request.headers.get("x-api-key", "").strip()
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )

    ctx = await verify_key(db, presented, required_scope="govern:write")
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )
    return ctx


def get_preflight_service() -> PreflightService:
    """Redis-backed pre-flight prediction service (Phase 2.25)."""

    from axiom.services.preflight.cache import PreflightCache
    from axiom.services.preflight.service import PreflightService
    from axiom.services.redis_client import get_redis

    return PreflightService(PreflightCache(get_redis()))


class RequireProjectRole:
    def __init__(self, minimum: MemberRole) -> None:
        self.minimum = minimum

    async def __call__(
        self,
        project_id: UUID,
        db: Annotated[AsyncSession, Depends(get_db)],
        user: Annotated[User, Depends(get_current_user)],
    ) -> ProjectMember:
        membership = await members_service.get_membership(
            db,
            project_id=project_id,
            user_id=user.id,
        )
        if membership is None:
            raise errors.ProjectNotFoundError("Project not found.")
        if _rank(membership.role) < _rank(self.minimum.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient project role",
            )
        return membership


async def resolve_created_by_user_id(
    request: Request, db: AsyncSession, ctx: APIKeyContext
) -> UUID:
    """JWT session → user id; API key / no JWT → project owner (for audit FK)."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw = auth_header[7:].strip()
        if raw and not raw.startswith(("axm_live_", "axm_test_")):
            try:
                payload = decode_token(raw)
            except ValueError:
                pass
            else:
                if payload.get("type") == "access":
                    try:
                        return UUID(str(payload["sub"]))
                    except (TypeError, ValueError):
                        pass
    project = await projects_service.get_project(db, ctx.project_id)
    return project.owner_user_id


async def created_by_user_id(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
) -> UUID:
    """FastAPI dependency: actor user id for audit columns (JWT vs API key)."""

    return await resolve_created_by_user_id(request, db, api_ctx)
