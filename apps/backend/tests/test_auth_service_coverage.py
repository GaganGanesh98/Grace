"""Targeted coverage for axiom.services.auth (DB + Redis integration)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from axiom.core import errors
from axiom.core.security import create_access_token, decode_token
from axiom.db import engine, session_scope
from axiom.models.project import Project
from axiom.models.user import User
from axiom.services import auth as auth_service
from axiom.services.redis_client import get_redis


async def _truncate_app_tables() -> None:
    stmt = text(
        "TRUNCATE agents, api_keys, policies, project_members, projects, "
        "audit_events, users RESTART IDENTITY CASCADE"
    )
    async with engine.begin() as conn:
        await conn.execute(stmt)


def _unique_email() -> str:
    return f"svc-{uuid4().hex}@example.com"


@pytest.fixture
async def isolated_db() -> None:
    await _truncate_app_tables()
    yield
    await _truncate_app_tables()


@pytest.mark.asyncio
async def test_signup_weak_password_no_letter() -> None:
    async with session_scope() as session:
        with pytest.raises(errors.WeakPasswordError, match="letter"):
            await auth_service.signup(
                session,
                email=_unique_email(),
                password="12345678",
                full_name="A",
            )


@pytest.mark.asyncio
async def test_signup_weak_password_no_digit() -> None:
    async with session_scope() as session:
        with pytest.raises(errors.WeakPasswordError, match="number"):
            await auth_service.signup(
                session,
                email=_unique_email(),
                password="onlyletters",
                full_name="A",
            )


@pytest.mark.asyncio
async def test_signup_weak_password_too_short() -> None:
    async with session_scope() as session:
        with pytest.raises(errors.WeakPasswordError, match="8 characters"):
            await auth_service.signup(
                session,
                email=_unique_email(),
                password="ab1",
                full_name="A",
            )


@pytest.mark.asyncio
async def test_signup_duplicate_email_service() -> None:
    email = _unique_email()
    async with session_scope() as session:
        await auth_service.signup(session, email=email, password="password1a", full_name="A")
    async with session_scope() as session:
        with pytest.raises(errors.DuplicateEmailError):
            await auth_service.signup(session, email=email, password="password1b", full_name="B")


@pytest.mark.asyncio
async def test_signup_first_user_creates_personal_project(isolated_db: object) -> None:
    _ = isolated_db
    email = _unique_email()
    async with session_scope() as session:
        user, _a, _r = await auth_service.signup(
            session,
            email=email,
            password="password1a",
            full_name="Founder",
        )
    async with session_scope() as session:
        slug = (
            await session.execute(select(Project.slug).where(Project.owner_user_id == user.id))
        ).scalar_one()
        assert slug.startswith("personal")


@pytest.mark.asyncio
async def test_login_clears_failed_attempt_counters() -> None:
    email = _unique_email()
    async with session_scope() as session:
        await auth_service.signup(session, email=email, password="password1a", full_name="A")
    fails_before = await auth_service.record_failed_login(email)
    assert fails_before >= 1
    async with session_scope() as session:
        await auth_service.login(session, email=email, password="password1a")
    fails_after = await auth_service.record_failed_login(email)
    assert fails_after == 1


@pytest.mark.asyncio
async def test_login_unknown_user_increments_failures() -> None:
    email = _unique_email()
    with pytest.raises(errors.InvalidCredentialsError):
        async with session_scope() as session:
            await auth_service.login(session, email=email, password="password1a")
    redis = get_redis()
    raw = await redis.get(f"lockout:fails:{email.lower()}")
    assert raw is not None and int(raw) >= 1


@pytest.mark.asyncio
async def test_refresh_invalid_jwt() -> None:
    async with session_scope() as session:
        with pytest.raises(errors.InvalidTokenError):
            await auth_service.refresh_tokens(session, refresh_token="not-a-jwt")


@pytest.mark.asyncio
async def test_refresh_wrong_token_type() -> None:
    async with session_scope() as session:
        user, _, _r = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
        access = create_access_token(str(user.id))
    async with session_scope() as session:
        with pytest.raises(errors.InvalidTokenError):
            await auth_service.refresh_tokens(session, refresh_token=access)


@pytest.mark.asyncio
async def test_refresh_reuse_old_token_after_rotation() -> None:
    async with session_scope() as session:
        _user, _, refresh = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
    async with session_scope() as session:
        _, _, new_refresh = await auth_service.refresh_tokens(session, refresh_token=refresh)
    async with session_scope() as session:
        with pytest.raises(errors.RefreshTokenRevokedError):
            await auth_service.refresh_tokens(session, refresh_token=refresh)
    assert new_refresh


@pytest.mark.asyncio
async def test_refresh_stored_user_id_mismatch() -> None:
    async with session_scope() as session:
        _user, _, refresh = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
        payload = decode_token(refresh)
        jti = str(payload["jti"])
        redis = get_redis()
        await redis.set(f"refresh:{jti}", str(uuid4()), ex=60)
    async with session_scope() as session:
        with pytest.raises(errors.InvalidTokenError):
            await auth_service.refresh_tokens(session, refresh_token=refresh)


@pytest.mark.asyncio
async def test_refresh_user_deleted() -> None:
    async with session_scope() as session:
        user, _, refresh = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
        uid = user.id
    async with session_scope() as session:
        u = await session.get(User, uid)
        assert u is not None
        u.deleted_at = u.created_at
    async with session_scope() as session:
        with pytest.raises(errors.InvalidTokenError):
            await auth_service.refresh_tokens(session, refresh_token=refresh)


@pytest.mark.asyncio
async def test_refresh_user_inactive() -> None:
    async with session_scope() as session:
        user, _, refresh = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
        uid = user.id
    async with session_scope() as session:
        u = await session.get(User, uid)
        assert u is not None
        u.is_active = False
    async with session_scope() as session:
        with pytest.raises(errors.InvalidTokenError):
            await auth_service.refresh_tokens(session, refresh_token=refresh)


@pytest.mark.asyncio
async def test_refresh_redis_returns_bytes_branch() -> None:
    async with session_scope() as session:
        user, _, refresh = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
        uid = str(user.id).encode()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=uid)
    mock_redis.delete = AsyncMock()
    mock_redis.set = AsyncMock()

    with patch("axiom.services.auth.get_redis", return_value=mock_redis):
        async with session_scope() as session:
            u, _a, _nr = await auth_service.refresh_tokens(session, refresh_token=refresh)
            assert u.id == user.id


@pytest.mark.asyncio
async def test_logout_ignores_invalid_refresh() -> None:
    await auth_service.logout(refresh_token="totally-invalid")


@pytest.mark.asyncio
async def test_logout_ignores_access_token() -> None:
    async with session_scope() as session:
        user, _, _r = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
        access = create_access_token(str(user.id))
    await auth_service.logout(refresh_token=access)


@pytest.mark.asyncio
async def test_get_user_by_id_missing() -> None:
    async with session_scope() as session:
        with pytest.raises(errors.UserNotFoundError):
            await auth_service.get_user_by_id(session, uuid4())


@pytest.mark.asyncio
async def test_get_user_by_id_soft_deleted() -> None:
    async with session_scope() as session:
        user, _, _r = await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="A",
        )
        uid = user.id
    async with session_scope() as session:
        u = await session.get(User, uid)
        assert u is not None
        u.deleted_at = u.created_at
    async with session_scope() as session:
        with pytest.raises(errors.UserNotFoundError):
            await auth_service.get_user_by_id(session, uid)


@pytest.mark.asyncio
async def test_ensure_google_user_updates_existing_by_sub() -> None:
    sub = f"sub-{uuid4().hex}"
    email1 = _unique_email()
    async with session_scope() as session:
        await auth_service.ensure_google_user(
            session,
            email=email1,
            google_sub=sub,
            full_name="G1",
            avatar_url=None,
        )
    email2 = _unique_email()
    async with session_scope() as session:
        user, _a, _r = await auth_service.ensure_google_user(
            session,
            email=email2,
            google_sub=sub,
            full_name="G2",
            avatar_url="https://example.com/a.png",
        )
        assert user.email == email2
        assert user.full_name == "G2"


@pytest.mark.asyncio
async def test_ensure_google_user_rejects_deleted_google_account() -> None:
    sub = f"sub-{uuid4().hex}"
    async with session_scope() as session:
        user, _, _ = await auth_service.ensure_google_user(
            session,
            email=_unique_email(),
            google_sub=sub,
            full_name="G",
            avatar_url=None,
        )
        user.deleted_at = user.created_at
    async with session_scope() as session:
        with pytest.raises(errors.InvalidCredentialsError, match="deleted"):
            await auth_service.ensure_google_user(
                session,
                email=_unique_email(),
                google_sub=sub,
                full_name="G",
                avatar_url=None,
            )


@pytest.mark.asyncio
async def test_ensure_google_user_links_email_account() -> None:
    email = _unique_email()
    async with session_scope() as session:
        await auth_service.signup(session, email=email, password="password1a", full_name="Local")
    sub = f"sub-{uuid4().hex}"
    async with session_scope() as session:
        user, _, _ = await auth_service.ensure_google_user(
            session,
            email=email,
            google_sub=sub,
            full_name="Linked",
            avatar_url=None,
        )
        assert user.google_sub == sub


@pytest.mark.asyncio
async def test_ensure_google_user_conflict_when_email_has_other_sub() -> None:
    email = _unique_email()
    sub_a = f"sub-a-{uuid4().hex}"
    sub_b = f"sub-b-{uuid4().hex}"
    async with session_scope() as session:
        await auth_service.ensure_google_user(
            session,
            email=email,
            google_sub=sub_a,
            full_name="A",
            avatar_url=None,
        )
    async with session_scope() as session:
        with pytest.raises(errors.ConflictError):
            await auth_service.ensure_google_user(
                session,
                email=email,
                google_sub=sub_b,
                full_name="B",
                avatar_url=None,
            )


@pytest.mark.asyncio
async def test_ensure_google_new_user_skips_founding_when_users_exist(isolated_db: object) -> None:
    _ = isolated_db
    async with session_scope() as session:
        await auth_service.signup(
            session,
            email=_unique_email(),
            password="password1a",
            full_name="First",
        )
    async with session_scope() as session:
        user, _, _ = await auth_service.ensure_google_user(
            session,
            email=_unique_email(),
            google_sub=f"sub-{uuid4().hex}",
            full_name="Google",
            avatar_url=None,
        )
    async with session_scope() as session:
        n = (
            await session.execute(
                select(Project.id).where(Project.owner_user_id == user.id),
            )
        ).all()
        assert n == []


@pytest.mark.asyncio
async def test_ensure_google_founding_project_when_first_account(isolated_db: object) -> None:
    _ = isolated_db
    email = _unique_email()
    async with session_scope() as session:
        user, _, _ = await auth_service.ensure_google_user(
            session,
            email=email,
            google_sub=f"sub-{uuid4().hex}",
            full_name="Solo Google",
            avatar_url=None,
        )
    async with session_scope() as session:
        slug = (
            await session.execute(select(Project.slug).where(Project.owner_user_id == user.id))
        ).scalar_one()
        assert slug.startswith("personal")


@pytest.mark.asyncio
async def test_signup_personal_slug_increments_when_slug_still_taken(isolated_db: object) -> None:
    _ = isolated_db
    email1 = _unique_email()
    async with session_scope() as session:
        await auth_service.signup(session, email=email1, password="password1a", full_name="A")
        uid = (await session.execute(select(User.id).where(User.email == email1))).scalar_one()
        pid = (
            await session.execute(select(Project.id).where(Project.owner_user_id == uid))
        ).scalar_one()
        proj = await session.get(Project, pid)
        assert proj is not None
        now = datetime.now(UTC)
        proj.deleted_at = now
        user = await session.get(User, uid)
        assert user is not None
        user.deleted_at = now
    email2 = _unique_email()
    async with session_scope() as session:
        user2, _, _ = await auth_service.signup(
            session,
            email=email2,
            password="password1b",
            full_name="B",
        )
    async with session_scope() as session:
        slug = (
            await session.execute(select(Project.slug).where(Project.owner_user_id == user2.id))
        ).scalar_one()
        assert slug.startswith("personal-")


@pytest.mark.asyncio
async def test_ensure_google_personal_slug_increments_when_taken(isolated_db: object) -> None:
    _ = isolated_db
    email1 = _unique_email()
    async with session_scope() as session:
        await auth_service.ensure_google_user(
            session,
            email=email1,
            google_sub=f"sub-{uuid4().hex}",
            full_name="G1",
            avatar_url=None,
        )
        uid = (await session.execute(select(User.id).where(User.email == email1))).scalar_one()
        pid = (
            await session.execute(select(Project.id).where(Project.owner_user_id == uid))
        ).scalar_one()
        proj = await session.get(Project, pid)
        assert proj is not None
        now = datetime.now(UTC)
        proj.deleted_at = now
        user = await session.get(User, uid)
        assert user is not None
        user.deleted_at = now
    email2 = _unique_email()
    async with session_scope() as session:
        user2, _, _ = await auth_service.ensure_google_user(
            session,
            email=email2,
            google_sub=f"sub-{uuid4().hex}",
            full_name="G2",
            avatar_url=None,
        )
    async with session_scope() as session:
        slug = (
            await session.execute(select(Project.slug).where(Project.owner_user_id == user2.id))
        ).scalar_one()
        assert slug.startswith("personal-")


@pytest.mark.asyncio
async def test_login_wrong_password_service() -> None:
    email = _unique_email()
    async with session_scope() as session:
        await auth_service.signup(session, email=email, password="password1a", full_name="A")
    async with session_scope() as session:
        with pytest.raises(errors.InvalidCredentialsError):
            await auth_service.login(session, email=email, password="wrongpass1")


@pytest.mark.asyncio
async def test_login_inactive_runs_password_check_branch() -> None:
    email = _unique_email()
    async with session_scope() as session:
        await auth_service.signup(session, email=email, password="password1a", full_name="A")
        uid = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        user = await session.get(User, uid)
        assert user is not None
        user.is_active = False
    async with session_scope() as session:
        with pytest.raises(errors.InactiveUserError):
            await auth_service.login(session, email=email, password="password1a")
