"""Agent run lifecycle: queue, tokens, cancel (Phase 6.5)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from jose import jwt
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.core import errors
from axiom.models.agent_definition import AgentDefinition
from axiom.models.agent_run import AgentRun, AgentRunStatus
from axiom.services.redis_client import get_redis
from axiom.services.events import schedule_run_completed
from axiom.utils.ids import new_uuidv7_str

logger = structlog.get_logger(__name__)

QUEUE_PENDING = "axiom:agent_runs:pending"


def _ws_token(run_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=5)
    payload = {
        "sub": str(run_id),
        "iat": now,
        "exp": expire,
        "jti": new_uuidv7_str(),
        "typ": "agent_run_ws",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def _hash_ws_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AgentRunService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        agent_definition_id: UUID,
        input_payload: dict[str, object] | None,
    ) -> tuple[AgentRun, str, str]:
        """Returns (run, ws_token_plaintext, correlation_id)."""
        correlation_id = new_uuidv7_str()
        run = AgentRun(
            project_id=project_id,
            agent_definition_id=agent_definition_id,
            status=AgentRunStatus.PENDING.value,
            correlation_id=correlation_id,
            input_payload=input_payload,
            receipt_ids=[],
            artifacts=[],
        )
        self._session.add(run)
        await self._session.flush()

        token = _ws_token(run.id)
        run.ws_token_hash = _hash_ws_token(token)

        # Commit BEFORE publishing so the worker can't pick up the run_id
        # before the row is visible to other connections. Without this, the
        # worker's BRPOP races the outer get_db() commit and fails with
        # agent_worker.run_not_found.
        await self._session.commit()

        redis = get_redis()
        await redis.lpush(
            QUEUE_PENDING,
            json.dumps({"run_id": str(run.id), "correlation_id": correlation_id}),
        )
        return run, token, correlation_id

    async def get(self, *, project_id: UUID, run_id: UUID) -> AgentRun:
        row = await self._session.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.project_id == project_id)
        )
        if row is None:
            raise errors.ProjectNotFoundError("Agent run not found.")
        return row

    async def list(
        self,
        *,
        project_id: UUID,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        q: str | None = None,
    ) -> tuple[list[AgentRun], int]:
        conds: list = [AgentRun.project_id == project_id]
        if status in {s.value for s in AgentRunStatus}:
            conds.append(AgentRun.status == status)
        if q and q.strip():
            term = f"%{q.strip()}%"
            ad_sub = select(AgentDefinition.id).where(
                AgentDefinition.project_id == project_id,
                AgentDefinition.name.ilike(term),
            )
            search = or_(
                cast(AgentRun.id, String).ilike(term),
                AgentRun.input_payload["goal"].as_string().ilike(term),  # type: ignore[union-attr]
                AgentRun.agent_definition_id.in_(ad_sub),  # type: ignore[attr-defined]
            )
            conds.append(search)
        w = and_(*conds)
        total = int(
            await self._session.scalar(select(func.count()).select_from(AgentRun).where(w)) or 0
        )
        rows = await self._session.scalars(
            select(AgentRun)
            .where(w)
            .order_by(AgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows), total

    async def cancel(self, *, project_id: UUID, run_id: UUID) -> AgentRun:
        run = await self.get(project_id=project_id, run_id=run_id)
        if run.status in (AgentRunStatus.SUCCEEDED.value, AgentRunStatus.FAILED.value):
            return run
        run.status = AgentRunStatus.CANCELLED.value
        redis = get_redis()
        payload = json.dumps({"type": "status_change", "status": AgentRunStatus.CANCELLED.value})
        await redis.publish(f"axiom:agent_runs:events:{run_id}", payload)
        await self._session.commit()
        schedule_run_completed(
            run.project_id,
            run_id=run.id,
            status="cancelled",
        )
        logger.info("agent_run.cancelled", run_id=str(run_id), project_id=str(project_id))
        return run

    def mint_ws_token(self, run: AgentRun) -> str:
        """Mint a fresh WS JWT and record its hash on the run row as last-issued audit."""
        token = _ws_token(run.id)
        run.ws_token_hash = _hash_ws_token(token)
        return token
