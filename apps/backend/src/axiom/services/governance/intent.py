"""Stage 1: intent declaration."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import GovernanceIntent
from axiom.schemas.governance import GovernRequest

logger = structlog.get_logger(__name__)


async def declare_intent(
    db: AsyncSession,
    project_id: UUID,
    request: GovernRequest,
    *,
    chain_id: UUID | None = None,
) -> GovernanceIntent:
    intent = GovernanceIntent(
        project_id=project_id,
        agent_id=request.agent_id,
        action_type=request.action_type,
        target=request.target,
        parameters=dict(request.parameters),
        risk_declared=request.risk,
        mode=request.mode,
        extra_metadata=dict(request.metadata),
        chain_id=chain_id,
    )
    db.add(intent)
    await db.flush()
    logger.info(
        "governance.intent.declared",
        intent_id=str(intent.id),
        project_id=str(project_id),
        agent_id=request.agent_id,
        action_type=request.action_type,
        risk=request.risk,
        mode=request.mode,
    )
    return intent
