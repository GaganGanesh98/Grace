from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.core.security import hash_password, verify_password
from axiom.models.user import User


async def update_profile(
    session: AsyncSession,
    user: User,
    *,
    full_name: str | None,
    avatar_url: str | None,
) -> User:
    if full_name is not None:
        user.full_name = full_name
    if avatar_url is not None:
        user.avatar_url = avatar_url
    return user


async def change_password(
    session: AsyncSession,
    user: User,
    *,
    current_password: str | None,
    new_password: str,
) -> None:
    if len(new_password) < 8:
        raise errors.WeakPasswordError("Password must be at least 8 characters.")
    if user.password_hash is None:
        user.password_hash = hash_password(new_password)
        return
    if current_password is None:
        raise errors.ValidationError("Current password is required.")
    if not verify_password(current_password, user.password_hash):
        raise errors.InvalidCredentialsError("Current password is incorrect.")
    user.password_hash = hash_password(new_password)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    row: object | None = await session.scalar(
        select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    )
    if row is None:
        return None
    if not isinstance(row, User):
        msg = "Unexpected result type from database query."
        raise TypeError(msg)
    return row


async def create_placeholder_user(session: AsyncSession, *, email: str) -> User:
    user = User(
        email=email.lower(),
        password_hash=None,
        full_name=None,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)
