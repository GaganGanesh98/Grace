"""WebSocket bridge: JWT validation (sig + exp + sub), bounded replay, live pub/sub."""

from __future__ import annotations

from uuid import UUID

import structlog
from redis.asyncio import Redis
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from axiom.core.security import decode_token
from axiom.services.redis_client import get_redis

logger = structlog.get_logger(__name__)

EVENT_LOG_PREFIX = "axiom:agent_runs:events_log:"
EVENT_CHAN_PREFIX = "axiom:agent_runs:events:"


async def _load_replay(redis: Redis, run_id: UUID) -> list[str]:
    """Historical JSON strings oldest-first (Redis list is newest-first from LPUSH)."""

    key = f"{EVENT_LOG_PREFIX}{run_id}"
    raw = await redis.lrange(key, 0, 49)
    out: list[str] = []
    for item in reversed(raw):
        if isinstance(item, (bytes, bytearray)):
            out.append(item.decode("utf-8"))
        else:
            out.append(str(item))
    return out


async def _validate_token(run_id: UUID, token: str | None) -> bool:
    """JWT-only check. No DB hash lookup — a valid signature + exp + typ + sub
    is sufficient proof that the backend minted this token for this run, and
    lets multiple concurrent connections (React Strict Mode, refresh, tabs)
    share the same token within its 5-minute expiry window.
    """

    if not token:
        return False
    try:
        payload = decode_token(token)
    except ValueError:
        return False
    if str(payload.get("typ")) != "agent_run_ws":
        return False
    return str(payload.get("sub")) == str(run_id)


async def handle_run_stream(
    websocket: WebSocket,
    run_id: UUID,
    token: str | None = None,
) -> None:
    """Validate WS JWT + stored hash, replay recent events, then stream live pub/sub."""

    redis = get_redis()
    if not await _validate_token(run_id, token):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        for payload in await _load_replay(redis, run_id):
            if websocket.application_state != WebSocketState.CONNECTED:
                return
            await websocket.send_text(payload)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("websocket.replay_failed", error=str(exc))

    pubsub = redis.pubsub()
    chan = f"{EVENT_CHAN_PREFIX}{run_id}"
    await pubsub.subscribe(chan)

    try:
        async for raw in pubsub.listen():
            if raw is None:
                continue
            if raw.get("type") != "message":
                continue
            data = raw.get("data")
            text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data)
            if websocket.application_state != WebSocketState.CONNECTED:
                break
            await websocket.send_text(text)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("websocket.live_failed", error=str(exc))
    finally:
        await pubsub.unsubscribe(chan)
        await pubsub.close()


stream_handler = handle_run_stream
