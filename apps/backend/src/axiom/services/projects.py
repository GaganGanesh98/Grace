from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.project import Project
from axiom.models.user import User
from axiom.services import audit as audit_service
from axiom.services.auth import _slugify


async def create_project(
    session: AsyncSession,
    *,
    owner: User,
    name: str,
    description: str | None,
    slug: str | None,
) -> Project:
    base = _slugify(slug or name)
    last_error: IntegrityError | None = None
    for attempt in range(50):
        candidate = base if attempt == 0 else f"{base}-{attempt}"
        project = Project(
            slug=candidate,
            name=name,
            description=description,
            owner_user_id=owner.id,
        )
        try:
            async with session.begin_nested():
                session.add(project)
                await session.flush()
        except IntegrityError as exc:
            last_error = exc
            continue
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=owner.id,
                role=MemberRole.OWNER.value,
                invited_by_user_id=None,
            )
        )
        await audit_service.record_event(
            session,
            event_type="project.created",
            actor_user_id=owner.id,
            project_id=project.id,
            target_type="project",
            target_id=project.id,
            metadata={"slug": candidate},
        )
        return project
    raise errors.DuplicateSlugError("Could not allocate a unique project slug.") from last_error


async def list_projects_for_user(
    session: AsyncSession,
    *,
    user_id: UUID,
    offset: int,
    limit: int,
) -> tuple[list[Project], int]:
    cond = (
        Project.deleted_at.is_(None),
        Project.id.in_(select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)),
    )
    total = int(await session.scalar(select(func.count()).select_from(Project).where(*cond)) or 0)
    rows = await session.scalars(
        select(Project).where(*cond).order_by(Project.created_at.desc()).offset(offset).limit(limit)
    )
    return list(rows.unique()), total


async def get_project(session: AsyncSession, project_id: UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise errors.ProjectNotFoundError("Project not found.")
    return project


async def update_project(
    session: AsyncSession,
    project: Project,
    *,
    name: str | None,
    description: str | None,
) -> Project:
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    return project


async def soft_delete_project(session: AsyncSession, project: Project) -> None:
    project.deleted_at = datetime.now(UTC)
