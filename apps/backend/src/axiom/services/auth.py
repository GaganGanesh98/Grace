import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.core.security import (
    compare_digest_str,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password_or_dummy,
)
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.project import Project
from axiom.models.user import User
from axiom.services import audit as audit_service
from axiom.services.redis_client import get_redis

LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW_SECONDS = 900


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise errors.WeakPasswordError("Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise errors.WeakPasswordError("Password must include at least one letter and one number.")


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "project"


async def _refresh_ttl_seconds() -> int:
    from axiom.config import get_settings

    settings = get_settings()
    return int(settings.jwt_refresh_token_expire_days * 24 * 60 * 60)


async def _store_refresh(jti: str, user_id: UUID) -> None:
    redis = get_redis()
    ttl = await _refresh_ttl_seconds()
    await redis.set(f"refresh:{jti}", str(user_id), ex=ttl)


async def _delete_refresh(jti: str) -> None:
    redis = get_redis()
    await redis.delete(f"refresh:{jti}")


async def is_locked(email: str) -> bool:
    redis = get_redis()
    key = f"lockout:locked:{email.lower()}"
    exists = await redis.exists(key)
    return int(exists) == 1


async def record_failed_login(email: str) -> int:
    redis = get_redis()
    normalized = email.lower()
    fail_key = f"lockout:fails:{normalized}"
    fails = int(await redis.incr(fail_key))
    if fails == 1:
        await redis.expire(fail_key, LOCKOUT_WINDOW_SECONDS)
    if fails >= LOCKOUT_THRESHOLD:
        await redis.set(
            f"lockout:locked:{normalized}",
            "1",
            ex=LOCKOUT_WINDOW_SECONDS,
        )
    return fails


async def clear_failed_logins(email: str) -> None:
    redis = get_redis()
    normalized = email.lower()
    await redis.delete(f"lockout:fails:{normalized}", f"lockout:locked:{normalized}")


async def signup(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None,
) -> tuple[User, str, str]:
    _validate_password_strength(password)
    normalized = email.lower()
    existing = await session.scalar(
        select(User).where(User.email == normalized, User.deleted_at.is_(None))
    )
    if existing is not None:
        raise errors.DuplicateEmailError("Email already registered.")

    count_stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    prior_count = int(await session.scalar(count_stmt) or 0)

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        full_name=full_name,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    if prior_count == 0:
        base_slug = "personal"
        slug = base_slug
        suffix = 0
        while await session.scalar(select(Project.id).where(Project.slug == slug)) is not None:
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        project = Project(
            slug=slug,
            name="Personal",
            description=None,
            owner_user_id=user.id,
        )
        session.add(project)
        await session.flush()
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=user.id,
                role=MemberRole.OWNER.value,
                invited_by_user_id=None,
            )
        )
        await audit_service.record_event(
            session,
            event_type="user.signup.founding",
            actor_user_id=user.id,
            project_id=project.id,
            target_type="project",
            target_id=project.id,
            metadata={"slug": slug},
        )

    await audit_service.record_event(
        session,
        event_type="user.signup",
        actor_user_id=user.id,
        project_id=None,
        target_type="user",
        target_id=user.id,
        metadata={},
    )

    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    payload = decode_token(refresh)
    jti = str(payload["jti"])
    await _store_refresh(jti, user.id)
    return user, access, refresh


async def login(session: AsyncSession, *, email: str, password: str) -> tuple[User, str, str]:
    normalized = email.lower()
    if await is_locked(normalized):
        raise errors.AccountLockedError(
            "Too many failed attempts. Try again in 15 minutes.",
        )
    user = await session.scalar(
        select(User).where(User.email == normalized, User.deleted_at.is_(None))
    )
    if user is None:
        verify_password_or_dummy(password, None)
        await record_failed_login(normalized)
        raise errors.InvalidCredentialsError("Invalid email or password.")
    if not user.is_active:
        verify_password_or_dummy(password, user.password_hash)
        await record_failed_login(normalized)
        raise errors.InactiveUserError("Account is inactive.")
    if not verify_password_or_dummy(password, user.password_hash):
        await record_failed_login(normalized)
        raise errors.InvalidCredentialsError("Invalid email or password.")

    await clear_failed_logins(normalized)
    user.last_login_at = datetime.now(UTC)
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    payload = decode_token(refresh)
    jti = str(payload["jti"])
    await _store_refresh(jti, user.id)
    return user, access, refresh


async def refresh_tokens(session: AsyncSession, *, refresh_token: str) -> tuple[User, str, str]:
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise errors.InvalidTokenError("Invalid refresh token.") from exc
    if payload.get("type") != "refresh":
        raise errors.InvalidTokenError("Invalid refresh token.")
    jti = str(payload.get("jti", ""))
    sub = str(payload.get("sub", ""))
    redis = get_redis()
    stored_raw = await redis.get(f"refresh:{jti}")
    if stored_raw is None:
        raise errors.RefreshTokenRevokedError("Refresh token revoked or expired.")
    if isinstance(stored_raw, bytes | bytearray):
        stored = stored_raw.decode("utf-8")
    else:
        stored = str(stored_raw)
    user_id = UUID(sub)
    if not compare_digest_str(stored, str(user_id)):
        raise errors.InvalidTokenError("Invalid refresh token.")

    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise errors.InvalidTokenError("Invalid refresh token.")

    await _delete_refresh(jti)
    access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))
    new_payload = decode_token(new_refresh)
    new_jti = str(new_payload["jti"])
    await _store_refresh(new_jti, user.id)
    return user, access, new_refresh


async def logout(*, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        return
    if payload.get("type") != "refresh":
        return
    jti = str(payload.get("jti", ""))
    await _delete_refresh(jti)


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise errors.UserNotFoundError("User not found.")
    return user


async def ensure_google_user(
    session: AsyncSession,
    *,
    email: str,
    google_sub: str,
    full_name: str | None,
    avatar_url: str | None,
) -> tuple[User, str, str]:
    normalized = email.lower()
    user = await session.scalar(select(User).where(User.google_sub == google_sub))
    if user is not None:
        if user.deleted_at is not None:
            raise errors.InvalidCredentialsError("Account is deleted.")
        user.email = normalized
        user.full_name = full_name or user.full_name
        user.avatar_url = avatar_url or user.avatar_url
        user.last_login_at = datetime.now(UTC)
    else:
        user = await session.scalar(
            select(User).where(User.email == normalized, User.deleted_at.is_(None)),
        )
        if user is not None:
            if user.google_sub is not None and user.google_sub != google_sub:
                raise errors.ConflictError("Email already linked to another Google account.")
            user.google_sub = google_sub
            user.full_name = full_name or user.full_name
            user.avatar_url = avatar_url or user.avatar_url
            user.last_login_at = datetime.now(UTC)
        else:
            count_stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
            prior_count = int(await session.scalar(count_stmt) or 0)
            user = User(
                email=normalized,
                password_hash=None,
                full_name=full_name,
                avatar_url=avatar_url,
                google_sub=google_sub,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            if prior_count == 0:
                base_slug = "personal"
                slug = base_slug
                suffix = 0
                while (
                    await session.scalar(select(Project.id).where(Project.slug == slug)) is not None
                ):
                    suffix += 1
                    slug = f"{base_slug}-{suffix}"
                project = Project(
                    slug=slug,
                    name="Personal",
                    description=None,
                    owner_user_id=user.id,
                )
                session.add(project)
                await session.flush()
                session.add(
                    ProjectMember(
                        project_id=project.id,
                        user_id=user.id,
                        role=MemberRole.OWNER.value,
                        invited_by_user_id=None,
                    )
                )

    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    payload = decode_token(refresh)
    jti = str(payload["jti"])
    await _store_refresh(jti, user.id)
    return user, access, refresh
