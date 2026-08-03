from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.audit_event import AuditEvent


async def record_event(
    session: AsyncSession,
    *,
    event_type: str,
    actor_user_id: UUID | None,
    project_id: UUID | None,
    target_type: str | None,
    target_id: UUID | None,
    metadata: dict[str, Any],
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            project_id=project_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            metadata_=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
