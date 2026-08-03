"""Project-scoped events via Redis PUBLISH / SUBSCRIBE. Publish only after commit — schedule with schedule_* from routes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import orjson
import structlog
from redis.asyncio import Redis

from axiom.services.redis_client import get_redis

logger = structlog.get_logger(__name__)

# Channel: one global prefix + project UUID; keeps traffic isolated per project.
AXIOM_EVENTS_PREFIX = "axiom:events:"


def _iso_z(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def map_verdict_for_event(verdict_raw: str) -> str:
    """Map stored verdict to Phase 7.6 vocabulary (APPROVE, MODIFY, ESCALATE, DENY)."""
    m = (verdict_raw or "").lower().strip()
    if m in ("allow", "allowed", "approve", "approved"):
        return "APPROVE"
    if m in ("deny", "denied", "rejected", "rejected_approval", "deny_approval"):
        return "DENY"
    if m in ("hold", "escalate", "escalation", "shadow_hold"):
        return "ESCALATE"
    if m in ("modify", "modified"):
        return "MODIFY"
    return m.upper() if m else "DENY"


def _channel(project_id: UUID) -> str:
    return f"{AXIOM_EVENTS_PREFIX}{project_id}"


async def _publish(redis: Redis, project_id: UUID, envelope: dict[str, Any]) -> None:
    await redis.publish(_channel(project_id), orjson.dumps(envelope).decode())


async def publish_axiom_event(
    event_type: str, project_id: UUID, payload: dict[str, Any], *, at: datetime | None = None
) -> None:
    """Await after commit. Never raise."""
    at = at or datetime.now(UTC)
    envelope = {
        "type": event_type,
        "project_id": str(project_id),
        "ts": _iso_z(at),
        "payload": payload,
    }
    try:
        await _publish(get_redis(), project_id, envelope)
    except Exception as exc:  # noqa: BLE001
        logger.warning("axiom_event.publish_failed", type=event_type, project_id=str(project_id), error=str(exc))


def schedule_axiom_event(event_type: str, project_id: UUID, payload: dict[str, Any]) -> None:
    """Post-commit, publish-and-forget. Safe from async request handlers (running loop)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("axiom_event.no_event_loop", type=event_type)
        return
    t = loop.create_task(publish_axiom_event(event_type, project_id, payload))

    def _done(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except Exception:  # noqa: BLE001
            pass  # already logged in publish

    t.add_done_callback(_done)


def schedule_receipt_sealed(
    project_id: UUID, *, receipt_id: UUID, verdict_raw: str, agent_id: str
) -> None:
    schedule_axiom_event(
        "receipt.sealed",
        project_id,
        {
            "receipt_id": str(receipt_id),
            "verdict": map_verdict_for_event(verdict_raw),
            "agent_id": str(agent_id),
        },
    )


def schedule_approval_created(project_id: UUID, *, receipt_id: UUID, expires_at: datetime) -> None:
    schedule_axiom_event(
        "approval.created",
        project_id,
        {
            "receipt_id": str(receipt_id),
            "expires_at": _iso_z(expires_at),
        },
    )


def schedule_approval_resolved(
    project_id: UUID, *, receipt_id: UUID, resolution: str
) -> None:
    """resolution: approved | rejected | expired"""
    schedule_axiom_event(
        "approval.resolved",
        project_id,
        {
            "receipt_id": str(receipt_id),
            "resolution": resolution,
        },
    )


def schedule_run_started(project_id: UUID, *, run_id: UUID, agent_id: UUID) -> None:
    schedule_axiom_event(
        "run.started",
        project_id,
        {
            "run_id": str(run_id),
            "agent_id": str(agent_id),
        },
    )


def schedule_run_completed(project_id: UUID, *, run_id: UUID, status: str) -> None:
    """status: completed | failed | cancelled"""
    schedule_axiom_event(
        "run.completed",
        project_id,
        {
            "run_id": str(run_id),
            "status": status,
        },
    )


def schedule_policy_activated(project_id: UUID, *, policy_id: UUID, name: str) -> None:
    schedule_axiom_event(
        "policy.activated",
        project_id,
        {
            "policy_id": str(policy_id),
            "name": name,
        },
    )
