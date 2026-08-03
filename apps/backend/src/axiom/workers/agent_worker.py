"""Agent run worker: dequeue (optional), heartbeat, events, ReAct loop via governance gateway."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.db import session_scope
from axiom.models.agent_definition import AgentDefinition
from axiom.models.agent_run import AgentRun, AgentRunStatus
from axiom.models.api_key import ApiKey
from axiom.models.project import Project
from axiom.models.vault import VaultKey
from axiom.services.agent_runs import QUEUE_PENDING
from axiom.services.api_keys import create_api_key, revoke_api_key
from axiom.services.events import schedule_run_completed, schedule_run_started
from axiom.services.redis_client import get_redis
from axiom.workers.event_publisher import EventPublisher
from axiom.workers.heartbeat import Heartbeat
from axiom.workers.react_loop import run_react_loop

logger = structlog.get_logger(__name__)


async def _load_run_bundle(
    db: AsyncSession, *, run_id: UUID
) -> tuple[AgentRun, AgentDefinition, VaultKey] | None:
    run = await db.get(AgentRun, run_id)
    if run is None:
        return None
    definition = await db.get(AgentDefinition, run.agent_definition_id)
    if definition is None:
        return None
    vault_key = await db.get(VaultKey, definition.vault_key_id)
    if vault_key is None:
        return None
    return run, definition, vault_key


_WORKER_KEY_NAME = "agent-worker (auto-minted)"
_WORKER_SCOPES = ["govern:write"]


async def _resolve_project_gateway_key(
    db: AsyncSession, *, project_id: UUID, owner_user_id: UUID
) -> str:
    """Mint a live API key scoped to *project_id* for gateway auth.

    Revokes any previous worker-minted key for the project before minting so
    there is at most one active worker key per project.
    """

    rows = await db.scalars(
        select(ApiKey).where(
            ApiKey.project_id == project_id,
            ApiKey.name == _WORKER_KEY_NAME,
            ApiKey.revoked_at.is_(None),
        )
    )
    for old in rows:
        await revoke_api_key(db, old)

    _row, plaintext = await create_api_key(
        db,
        project_id=project_id,
        name=_WORKER_KEY_NAME,
        scopes=_WORKER_SCOPES,
        created_by_user_id=owner_user_id,
        expires_at=None,
    )
    return plaintext


async def process_run(run_id: str) -> None:  # noqa: PLR0915
    """Execute a single agent run: optional queue item is resolved by ``run_id`` string."""

    rid = UUID(run_id)

    async with session_scope() as db:
        # Belt + suspenders: producer commits before LPUSH, but a stray BRPOP
        # that still beats commit visibility retries briefly before giving up.
        bundle = None
        for attempt in range(3):
            bundle = await _load_run_bundle(db, run_id=rid)
            if bundle is not None:
                break
            if attempt < 2:
                await asyncio.sleep(0.2)
        if bundle is None:
            logger.warning("agent_worker.run_not_found", run_id=run_id)
            return
        run, _definition, _vault_key = bundle
        if run.status not in (AgentRunStatus.PENDING.value, AgentRunStatus.RUNNING.value):
            logger.info("agent_worker.run_not_runnable", run_id=run_id, status=run.status)
            return
        run.status = AgentRunStatus.RUNNING.value
        run.started_at = datetime.now(UTC)

        project = await db.get(Project, run.project_id)
        if project is None:
            run.status = AgentRunStatus.FAILED.value
            run.error_message = "Agent's project not found."
            run.completed_at = datetime.now(UTC)
            logger.error("agent_worker.project_not_found", project_id=str(run.project_id))
            return
        gateway_key = await _resolve_project_gateway_key(
            db, project_id=project.id, owner_user_id=project.owner_user_id
        )
        correlation_id = run.correlation_id

    project_id = run.project_id
    schedule_run_started(
        project_id, run_id=rid, agent_id=run.agent_definition_id
    )

    publisher = EventPublisher()
    await publisher.publish(
        rid,
        {
            "type": "run_started",
            "run_id": str(rid),
            "correlation_id": correlation_id,
        },
    )

    async def _db_heartbeat() -> None:
        async with session_scope() as sdb:
            row = await sdb.get(AgentRun, rid)
            if row is not None:
                row.last_heartbeat_at = datetime.now(UTC)

    hb = Heartbeat(rid, on_db_heartbeat=_db_heartbeat)
    hb.start()

    outcome: dict[str, Any] = {"ok": False, "error": "not_started"}
    try:
        async with httpx.AsyncClient() as client:

            async def _sink(event: dict[str, Any]) -> None:
                await publisher.publish(rid, event)

            async with session_scope() as db2:
                run2 = await db2.get(AgentRun, rid)
                def2 = await db2.get(AgentDefinition, run2.agent_definition_id) if run2 else None
                vk = await db2.get(VaultKey, def2.vault_key_id) if def2 else None
                if run2 is None or def2 is None or vk is None:
                    outcome = {"ok": False, "error": "run_bundle_lost"}
                else:
                    outcome = await run_react_loop(
                        run=run2,
                        definition=def2,
                        vault_key=vk,
                        httpx_client=client,
                        gateway_api_key=gateway_key,
                        event_sink=_sink,
                    )

        ok = bool(outcome.get("ok"))
        async with session_scope() as db3:
            row = await db3.get(AgentRun, rid)
            if row is not None:
                row.completed_at = datetime.now(UTC)
                rids = outcome.get("receipt_ids")
                row.receipt_ids = list(rids) if isinstance(rids, list) else []
                arts = outcome.get("artifacts")
                row.artifacts = list(arts) if isinstance(arts, list) else []
                total_tokens = outcome.get("total_tokens")
                if isinstance(total_tokens, int):
                    row.total_tokens = max(0, total_tokens)
                if ok:
                    row.status = AgentRunStatus.SUCCEEDED.value
                    row.final_output = outcome
                else:
                    row.status = AgentRunStatus.FAILED.value
                    err = outcome.get("error") or outcome.get("detail") or "failed"
                    row.error_message = str(err)
                    row.final_output = outcome
            if row is not None:
                comp_status = (
                    "completed" if row.status == AgentRunStatus.SUCCEEDED.value else "failed"
                )
                schedule_run_completed(row.project_id, run_id=row.id, status=comp_status)
        await publisher.publish(
            rid,
            {
                "type": "run_finished",
                "run_id": str(rid),
                "ok": ok,
            },
        )
    except Exception as exc:  # noqa: BLE001 — terminal failure; log + persist run state
        logger.exception("agent_worker.run_failed", run_id=run_id)
        ex_pid: UUID | None = None
        ex_row_id: UUID | None = None
        async with session_scope() as db4:
            row = await db4.get(AgentRun, rid)
            if row is not None:
                row.status = AgentRunStatus.FAILED.value
                row.error_message = str(exc)
                row.completed_at = datetime.now(UTC)
                ex_pid = row.project_id
                ex_row_id = row.id
        if ex_pid is not None and ex_row_id is not None:
            schedule_run_completed(ex_pid, run_id=ex_row_id, status="failed")
        await publisher.publish(
            rid,
            {"type": "run_failed", "run_id": str(rid), "error": str(exc)},
        )
    finally:
        await hb.stop()


async def drain_one_from_queue(timeout_seconds: float = 5.0) -> str | None:
    """Blocking pop of the next pending run id (JSON payload with ``run_id``)."""

    redis = get_redis()
    item = await redis.brpop(QUEUE_PENDING, timeout=timeout_seconds)
    if item is None:
        return None
    _key, raw = item
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    payload = json.loads(text)
    return str(payload["run_id"])


async def process_next_from_queue(timeout_seconds: float = 5.0) -> None:
    """Pick one run from the Redis pending list and execute it."""

    next_id = await drain_one_from_queue(timeout_seconds=timeout_seconds)
    if next_id is None:
        return
    await process_run(next_id)


def _log_startup_db_target() -> None:
    """Emit a redacted one-line breadcrumb of the DB the worker resolved.

    Guards against silent DB mismatch (e.g. worker spawned with TEST_DATABASE_URL
    from a prior pytest shell so it writes to axiom_test while the backend serves
    axiom — see agent_worker.run_not_found incident).
    """

    from urllib.parse import urlparse

    url = get_settings().database_url
    parsed = urlparse(url)
    host = parsed.hostname or "?"
    port = parsed.port or "?"
    name = (parsed.path or "/").lstrip("/") or "?"
    logger.info("agent_worker.startup", db_host=host, db_port=port, db_name=name)


def main() -> None:
    """Long-running queue consumer (5s BRPOP timeout per wait)."""

    import asyncio

    _log_startup_db_target()

    async def _loop() -> None:
        while True:
            await process_next_from_queue(timeout_seconds=5.0)

    asyncio.run(_loop())


if __name__ == "__main__":
    main()
