"""Mark stale running jobs as failed (worker heartbeat watchdog)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.agent_run import AgentRun, AgentRunStatus
from axiom.workers.event_publisher import EventPublisher

logger = structlog.get_logger(__name__)

STALE_AFTER = timedelta(seconds=60)


async def run_reaper_once(
    session: AsyncSession,
    publisher: EventPublisher | None = None,
) -> list[UUID]:
    """Fail running rows with missing or stale heartbeats; publish events."""
    pub = publisher if publisher is not None else EventPublisher()
    cutoff = datetime.now(UTC) - STALE_AFTER
    stmt = (
        update(AgentRun)
        .where(
            AgentRun.status == AgentRunStatus.RUNNING.value,
            (AgentRun.last_heartbeat_at.is_(None)) | (AgentRun.last_heartbeat_at < cutoff),
        )
        .values(
            status=AgentRunStatus.FAILED.value,
            error_message="worker_crashed",
            completed_at=func.now(),
        )
        .returning(AgentRun.id)
    )
    result = await session.execute(stmt)
    ids = [row[0] for row in result.fetchall()]
    for rid in ids:
        await pub.publish(
            rid,
            {
                "type": "status_change",
                "status": AgentRunStatus.FAILED.value,
                "reason": "worker_crashed",
            },
        )
    if ids:
        logger.warning("agent_run.reaper_reaped", count=len(ids), run_ids=[str(i) for i in ids])
    return ids


async def run_reaper_loop(
    *,
    session_ctx: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    interval_seconds: float = 30.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background loop (optional wiring from worker process)."""
    ev = stop_event if stop_event is not None else asyncio.Event()
    while not ev.is_set():
        try:
            await asyncio.wait_for(ev.wait(), timeout=interval_seconds)
            break
        except TimeoutError:
            pass
        async with session_ctx() as session:
            await run_reaper_once(session)
            await session.commit()
