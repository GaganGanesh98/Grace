"""Redis pub/sub + bounded event log for agent runs."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from axiom.services.redis_client import get_redis


class EventPublisher:
    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis if redis is not None else get_redis()

    async def publish(self, run_id: UUID, event: dict[str, Any]) -> None:
        payload = json.dumps(event, separators=(",", ":"))
        chan = f"axiom:agent_runs:events:{run_id}"
        await self._redis.publish(chan, payload)
        log_key = f"axiom:agent_runs:events_log:{run_id}"
        await self._redis.lpush(log_key, payload)
        await self._redis.ltrim(log_key, 0, 49)
        await self._redis.expire(log_key, 86400)
