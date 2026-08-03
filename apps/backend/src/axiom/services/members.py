from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from axiom.core import errors
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.project import Project
from axiom.models.user import User
from axiom.services import audit as audit_service
from axiom.services import users as users_service


def _rank(role: str) -> int:
    mapping = {
        MemberRole.MEMBER.value: 1,
        MemberRole.ADMIN.value: 2,
        MemberRole.OWNER.value: 3,
    }
    return mapping.get(role, 0)


def _meets_minimum(actor_role: str, minimum: MemberRole) -> bool:
    return _rank(actor_role) >= _rank(minimum.value)


async def get_membership(
    session: AsyncSession, *, project_id: UUID, user_id: UUID
) -> ProjectMember | None:
    row: object | None = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if row is None:
        return None
    if not isinstance(row, ProjectMember):
        msg = "Unexpected result type from database query."
        raise TypeError(msg)
    return row


async def list_members(
    session: AsyncSession, *, project_id: UUID, offset: int, limit: int
) -> tuple[list[ProjectMember], int]:
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.project_id == project_id)
        )
        or 0
    )
    rows = await session.scalars(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .options(selectinload(ProjectMember.user))
        .order_by(ProjectMember.joined_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows), total


async def invite_member(
    session: AsyncSession,
    *,
    project: Project,
    email: str,
    role: MemberRole,
    invited_by: User,
) -> ProjectMember:
    if role == MemberRole.OWNER:
        raise errors.ValidationError("Cannot invite a member as OWNER.")
    normalized = email.lower()
    user = await users_service.get_user_by_email(session, normalized)
    if user is None:
        user = await users_service.create_placeholder_user(session, email=normalized)
    existing = await get_membership(session, project_id=project.id, user_id=user.id)
    if existing is not None:
        raise errors.ConflictError("User is already a member of this project.")

    member = ProjectMember(
        project_id=project.id,
        user_id=user.id,
        role=role.value,
        invited_by_user_id=invited_by.id,
    )
    session.add(member)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise errors.ConflictError("User is already a member of this project.") from exc

    await audit_service.record_event(
        session,
        event_type="project.member.invited",
        actor_user_id=invited_by.id,
        project_id=project.id,
        target_type="project_member",
        target_id=member.id,
        metadata={"email": normalized, "role": role.value},
    )
    return member


async def update_member_role(
    session: AsyncSession,
    *,
    member: ProjectMember,
    new_role: MemberRole,
    actor: User,
    actor_membership: ProjectMember,
) -> ProjectMember:
    if new_role == MemberRole.OWNER:
        raise errors.ValidationError("Cannot assign OWNER via member update.")

    if member.role == MemberRole.OWNER.value:
        raise errors.PermissionDeniedError("Cannot change the project OWNER role.")

    if actor_membership.role == MemberRole.ADMIN.value:
        if member.role != MemberRole.MEMBER.value or new_role != MemberRole.ADMIN:
            raise errors.PermissionDeniedError(
                "Admins may only promote members from MEMBER to ADMIN.",
            )
    elif actor_membership.role != MemberRole.OWNER.value:
        raise errors.PermissionDeniedError("Only OWNER may change roles.")

    member.role = new_role.value
    await audit_service.record_event(
        session,
        event_type="project.member.role_changed",
        actor_user_id=actor.id,
        project_id=member.project_id,
        target_type="project_member",
        target_id=member.id,
        metadata={"role": new_role.value},
    )
    return member


async def remove_member(
    session: AsyncSession,
    *,
    member: ProjectMember,
    actor: User,
    actor_membership: ProjectMember,
) -> None:
    if member.role == MemberRole.OWNER.value:
        raise errors.PermissionDeniedError("Cannot remove the project OWNER.")
    if member.user_id == actor.id and actor_membership.role == MemberRole.OWNER.value:
        raise errors.PermissionDeniedError("OWNER cannot remove themselves without transfer.")

    if not _meets_minimum(actor_membership.role, MemberRole.ADMIN):
        raise errors.PermissionDeniedError("Insufficient permissions.")

    if actor_membership.role == MemberRole.ADMIN.value and member.role != MemberRole.MEMBER.value:
        raise errors.PermissionDeniedError("Admins can only remove MEMBER users.")

    await session.delete(member)
    await audit_service.record_event(
        session,
        event_type="project.member.removed",
        actor_user_id=actor.id,
        project_id=member.project_id,
        target_type="project_member",
        target_id=member.id,
        metadata={},
    )


async def get_member_by_id(
    session: AsyncSession, *, project_id: UUID, member_id: UUID
) -> ProjectMember:
    member = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.project_id == project_id,
        )
    )
    if member is None:
        raise errors.MemberNotFoundError("Member not found.")
    return member
