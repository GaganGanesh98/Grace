from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.models.agent import Agent
from axiom.services import audit as audit_service


async def list_agents(
    session: AsyncSession, *, project_id: UUID, offset: int, limit: int
) -> tuple[list[Agent], int]:
    cond = (Agent.project_id == project_id, Agent.deleted_at.is_(None))
    total = int(await session.scalar(select(func.count()).select_from(Agent).where(*cond)) or 0)
    rows = await session.scalars(
        select(Agent).where(*cond).order_by(Agent.created_at.desc()).offset(offset).limit(limit)
    )
    return list(rows), total


async def create_agent(
    session: AsyncSession,
    *,
    project_id: UUID,
    slug: str,
    name: str,
    description: str | None,
    agent_type: str,
    default_mode: str,
    metadata: dict[str, object],
    created_by_user_id: UUID,
) -> Agent:
    agent = Agent(
        project_id=project_id,
        slug=slug,
        name=name,
        description=description,
        agent_type=agent_type,
        default_mode=default_mode,
        metadata_=metadata,
        created_by_user_id=created_by_user_id,
    )
    session.add(agent)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise errors.ConflictError("Agent slug already exists in this project.") from exc
    await audit_service.record_event(
        session,
        event_type="agent.created",
        actor_user_id=created_by_user_id,
        project_id=project_id,
        target_type="agent",
        target_id=agent.id,
        metadata={"slug": slug},
    )
    return agent


async def get_agent(session: AsyncSession, *, project_id: UUID, agent_id: UUID) -> Agent:
    agent = await session.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.project_id == project_id,
            Agent.deleted_at.is_(None),
        )
    )
    if agent is None:
        raise errors.AgentNotFoundError("Agent not found.")
    return agent


async def update_agent(
    session: AsyncSession,
    agent: Agent,
    *,
    name: str | None,
    description: str | None,
    agent_type: str | None,
    default_mode: str | None,
    metadata: dict[str, object] | None,
    is_active: bool | None,
) -> Agent:
    if name is not None:
        agent.name = name
    if description is not None:
        agent.description = description
    if agent_type is not None:
        agent.agent_type = agent_type
    if default_mode is not None:
        agent.default_mode = default_mode
    if metadata is not None:
        agent.metadata_ = metadata
    if is_active is not None:
        agent.is_active = is_active
    return agent


async def soft_delete_agent(session: AsyncSession, agent: Agent) -> None:
    from datetime import UTC, datetime

    agent.deleted_at = datetime.now(UTC)
