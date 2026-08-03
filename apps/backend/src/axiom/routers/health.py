from collections.abc import Awaitable
from typing import Any

from fastapi import APIRouter, Response, status
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from axiom.db import engine
from axiom.schemas.common import DataEnvelope
from axiom.services.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=DataEnvelope[dict[str, str]])
async def healthz() -> DataEnvelope[dict[str, str]]:
    return DataEnvelope(data={"status": "ok"})


@router.get("/readyz", response_model=DataEnvelope[dict[str, Any]])
async def readyz(response: Response) -> DataEnvelope[dict[str, Any]]:
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except SQLAlchemyError:
        checks["db"] = "error"
    try:
        redis = get_redis()
        ping_result = redis.ping()
        pong = bool(await ping_result) if isinstance(ping_result, Awaitable) else bool(ping_result)
        checks["redis"] = "ok" if pong else "error"
    except RedisError:
        checks["redis"] = "error"
    ok = all(v == "ok" for v in checks.values())
    payload = {"status": "ready" if ok else "not_ready", "checks": checks}
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return DataEnvelope(data=payload)
