import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.models.api_key import ApiKey
from axiom.services import audit as audit_service


async def list_api_keys(
    session: AsyncSession, *, project_id: UUID, offset: int, limit: int
) -> tuple[list[ApiKey], int]:
    cond = (ApiKey.project_id == project_id,)
    total = int(await session.scalar(select(func.count()).select_from(ApiKey).where(*cond)) or 0)
    rows = await session.scalars(
        select(ApiKey).where(*cond).order_by(ApiKey.created_at.desc()).offset(offset).limit(limit)
    )
    return list(rows), total


async def create_api_key(
    session: AsyncSession,
    *,
    project_id: UUID,
    name: str,
    scopes: list[str],
    created_by_user_id: UUID,
    expires_at: datetime | None,
) -> tuple[ApiKey, str]:
    secret = secrets.token_urlsafe(32)
    full_key = f"axm_live_{secret}"
    digest = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    key_prefix = full_key[:16]
    row = ApiKey(
        project_id=project_id,
        name=name,
        key_prefix=key_prefix,
        key_hash=digest,
        scopes=scopes,
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    await session.flush()
    await audit_service.record_event(
        session,
        event_type="api_key.created",
        actor_user_id=created_by_user_id,
        project_id=project_id,
        target_type="api_key",
        target_id=row.id,
        metadata={"prefix": key_prefix},
    )
    return row, full_key


async def get_api_key(session: AsyncSession, *, project_id: UUID, key_id: UUID) -> ApiKey:
    key = await session.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project_id)
    )
    if key is None:
        raise errors.ApiKeyNotFoundError("API key not found.")
    return key


async def revoke_api_key(session: AsyncSession, key: ApiKey) -> None:
    key.revoked_at = datetime.now(UTC)
