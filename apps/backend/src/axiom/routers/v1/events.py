"""Phase 7.6 — project-scoped Server-Sent Events (Redis pub/sub)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

import orjson
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from axiom.config import get_settings
from axiom.deps import require_api_key_or_current_user
from axiom.services.api_key import APIKeyContext
from axiom.services.events.publisher import AXIOM_EVENTS_PREFIX
from axiom.services.redis_client import get_redis

router = APIRouter()
logger = structlog.get_logger(__name__)


def _iso_z_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fmt_sse(event: str, data: str) -> bytes:
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


@router.get("/events/stream")
async def events_stream(
    project_id: Annotated[UUID, Query(..., description="Project to subscribe to")],
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key_or_current_user)],
) -> StreamingResponse:
    """Long-lived SSE: `connected`, `ping` heartbeats, and domain events (event name = ``type``)."""
    if api_ctx.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this project",
        )

    settings = get_settings()
    interval = max(0.5, float(settings.events_heartbeat_interval_seconds))

    async def body() -> AsyncIterator[bytes]:
        stream_id = str(uuid4())
        init = orjson.dumps({"server_time": _iso_z_now(), "stream_id": stream_id}).decode()
        yield _fmt_sse("connected", init)

        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"{AXIOM_EVENTS_PREFIX}{project_id}")
        next_ping = time.monotonic() + interval
        try:
            while True:
                wait = min(1.0, max(0.01, next_ping - time.monotonic()))
                try:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=wait)
                except asyncio.CancelledError:
                    raise
                if time.monotonic() >= next_ping:
                    payload = orjson.dumps({"ts": _iso_z_now()}).decode()
                    yield _fmt_sse("ping", payload)
                    next_ping = time.monotonic() + interval
                if msg and msg.get("type") == "message":
                    raw = msg.get("data")
                    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                    try:
                        env = orjson.loads(text)
                    except (ValueError, TypeError):
                        logger.warning("axiom_event.sse_bad_json", project_id=str(project_id))
                        continue
                    ev = str(env.get("type", "message"))
                    yield _fmt_sse(ev, text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("axiom_event.sse_stream_error", project_id=str(project_id), error=str(exc))
            raise
        finally:
            try:
                await pubsub.unsubscribe(f"{AXIOM_EVENTS_PREFIX}{project_id}")
            except Exception:  # noqa: BLE001
                pass
            try:
                await pubsub.close()
            except Exception:  # noqa: BLE001
                pass

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
