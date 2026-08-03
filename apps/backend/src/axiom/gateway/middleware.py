"""Gateway authentication and Redis rate limiting."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.services.api_key import APIKeyContext, verify_key
from axiom.services.redis_client import get_redis


def _presented_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.headers.get("x-api-key", "").strip()


async def authenticate_gateway_request(db: AsyncSession, request: Request) -> APIKeyContext:
    presented = _presented_token(request)
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid or missing API key"},
        )
    ctx = await verify_key(db, presented, required_scope="govern:write")
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid or missing API key"},
        )
    return ctx


async def check_gateway_rate_limit(project_id: UUID) -> None:
    settings = get_settings()
    if not settings.gateway_enabled:
        return
    limit = settings.gateway_rate_limit_per_minute
    window = int(time.time() // 60)
    key = f"gateway:rl:{project_id}:{window}"
    redis = get_redis()
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, 120)
    if n > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limited", "message": "Too many gateway requests for this project"},
        )
