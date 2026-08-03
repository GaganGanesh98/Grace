"""Stage 2: context enrichment."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import GovernanceIntent, GovernanceVerdict
from axiom.models.project import Project


async def enrich_context(db: AsyncSession, intent: GovernanceIntent) -> dict:
    project = await db.get(Project, intent.project_id)
    project_settings: dict = dict(project.settings) if project is not None else {}

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    actions_today = int(
        await db.scalar(
            select(func.count())
            .select_from(GovernanceIntent)
            .where(
                GovernanceIntent.project_id == intent.project_id,
                GovernanceIntent.agent_id == intent.agent_id,
                GovernanceIntent.created_at >= today_start,
            )
        )
        or 0
    )

    violations = int(
        await db.scalar(
            select(func.count())
            .select_from(GovernanceVerdict)
            .join(GovernanceIntent, GovernanceVerdict.intent_id == GovernanceIntent.id)
            .where(
                GovernanceIntent.project_id == intent.project_id,
                GovernanceIntent.agent_id == intent.agent_id,
                GovernanceVerdict.verdict.in_(("deny", "hold")),
            )
        )
        or 0
    )

    return {
        "project_settings": project_settings,
        "agent_action_count_today": actions_today,
        "past_violations": violations,
    }
