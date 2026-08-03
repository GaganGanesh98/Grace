"""Redis + DB heartbeat for long-running agent work."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from axiom.services.redis_client import get_redis

HEARTBEAT_KEY_PREFIX = "axiom:agent_runs:heartbeat:"
HEARTBEAT_TTL_SECONDS = 30
HEARTBEAT_INTERVAL_SECONDS = 5
DB_HEARTBEAT_EVERY_N_TICKS = 3  # 5s * 3 = 15s


class Heartbeat:
    """Writes Redis heartbeat every 5s; optional DB callback every 15s."""

    def __init__(
        self,
        run_id: UUID,
        *,
        redis: Redis | None = None,
        on_db_heartbeat: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._run_id = run_id
        self._redis = redis if redis is not None else get_redis()
        self._on_db = on_db_heartbeat
        self._task: asyncio.Task[Any] | None = None
        self._stop = asyncio.Event()

    async def _loop(self) -> None:
        tick = 0
        key = f"{HEARTBEAT_KEY_PREFIX}{self._run_id}"
        while not self._stop.is_set():
            await self._redis.setex(key, HEARTBEAT_TTL_SECONDS, "1")
            tick += 1
            if tick % DB_HEARTBEAT_EVERY_N_TICKS == 0 and self._on_db is not None:
                await self._on_db()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=HEARTBEAT_INTERVAL_SECONDS)
            except TimeoutError:
                continue
            else:
                break

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
