"""Phase 7.6 — /v1/events/stream SSE (Redis pub/sub)."""

from __future__ import annotations

import os
import uuid

import orjson
import pytest
from httpx import ASGITransport, AsyncClient

from axiom.config import get_settings
from axiom.main import app
from axiom.services import redis_client
from axiom.services.events.publisher import AXIOM_EVENTS_PREFIX, publish_axiom_event
from tests.conftest import auth_headers, signup_user, unique_email, unique_slug

pytestmark = pytest.mark.asyncio


async def _bnext(ait) -> bytes:
    return await ait.__anext__()


def _set_heartbeat_2s() -> None:
    os.environ["AXIOM_EVENTS_HEARTBEAT_SECONDS"] = "2"
    get_settings.cache_clear()


def _reset_heartbeat_default() -> None:
    os.environ.pop("AXIOM_EVENTS_HEARTBEAT_SECONDS", None)
    get_settings.cache_clear()


@pytest.fixture
def heartbeat_2s() -> object:
    _set_heartbeat_2s()
    yield None
    _reset_heartbeat_default()


async def _h_and_pid() -> tuple[AsyncClient, dict[str, str], str]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    ac = AsyncClient(transport=transport, base_url="http://test")
    email = unique_email()
    tokens = await signup_user(ac, email, "password1a")
    h = auth_headers(tokens["access_token"])
    p = await ac.post(
        "/api/v1/projects", headers=h, json={"name": "E", "slug": unique_slug("e-proj")}
    )
    assert p.status_code == 201, p.text
    pid = p.json()["data"]["id"]
    return ac, h, pid


@pytest.mark.usefixtures("heartbeat_2s")
async def test_sse_stream_headers_and_initial_connected() -> None:
    ac, h, pid = await _h_and_pid()
    try:
        r = await ac.send(
            ac.build_request(
                "GET",
                f"http://test/v1/events/stream?project_id={pid}",
                headers={**h, "Accept": "text/event-stream"},
            ),
            stream=True,
        )
        assert r.status_code == 200, r.text
        assert (r.headers.get("content-type") or "").split(";")[0].strip() == "text/event-stream"
        assert "no-cache" in (r.headers.get("cache-control") or "").lower()
        assert (r.headers.get("connection") or "").lower() == "keep-alive"
        assert (r.headers.get("x-accel-buffering") or "") == "no"
        buf = b""
        itb = r.aiter_bytes()
        for _ in range(50):
            buf += await _bnext(itb)
            if b"event: connected" in buf and b"stream_id" in buf:
                break
        assert b"event: connected" in buf
        m = b""
        for line in buf.split(b"\n"):
            if line.startswith(b"data: "):
                m = line[6:].strip()
        assert m, buf
        d = orjson.loads(m)
        assert d.get("stream_id")
        assert d.get("server_time")
    finally:
        try:
            await r.aclose()
        except Exception:  # noqa: BLE001
            pass
        await ac.aclose()


@pytest.mark.usefixtures("heartbeat_2s")
async def test_heartbeat_multiple_pings() -> None:
    ac, h, pid = await _h_and_pid()
    r = None
    try:
        r = await ac.send(
            ac.build_request(
                "GET",
                f"http://test/v1/events/stream?project_id={pid}",
                headers={**h, "Accept": "text/event-stream"},
            ),
            stream=True,
        )
        assert r.status_code == 200
        buf = b""
        itb = r.aiter_bytes()
        while buf.count(b"event: ping") < 3:
            buf += await _bnext(itb)
        assert buf.count(b"event: ping") >= 3
    finally:
        if r:
            try:
                await r.aclose()
            except Exception:  # noqa: BLE001
                pass
        await ac.aclose()


async def test_subscriber_receives_same_project_event() -> None:
    ac, h, pid = await _h_and_pid()
    r = None
    try:
        pid_u = uuid.UUID(str(pid))
        r = await ac.send(
            ac.build_request(
                "GET",
                f"http://test/v1/events/stream?project_id={pid}",
                headers={**h, "Accept": "text/event-stream"},
            ),
            stream=True,
        )
        assert r.status_code == 200
        # Skip initial data until 'connected' consumed
        pre = b""
        it0 = r.aiter_bytes()
        for _ in range(50):
            pre += await _bnext(it0)
            if b"event: connected" in pre:
                break
        rid = str(uuid.uuid4())
        await publish_axiom_event(
            "receipt.sealed",
            pid_u,
            {
                "receipt_id": rid,
                "verdict": "DENY",
                "agent_id": str(uuid.uuid4()),
            },
        )
        more = b""
        for _ in range(100):
            more += await _bnext(it0)
            if rid.encode() in more and b"receipt.sealed" in more:
                break
        assert b"event: receipt.sealed" in more
        assert rid.encode() in more
    finally:
        if r:
            try:
                await r.aclose()
            except Exception:  # noqa: BLE001
                pass
        await ac.aclose()


async def test_does_not_receive_different_project_channel() -> None:
    ac1, h1, p1 = await _h_and_pid()
    p2 = str(uuid.uuid4())
    red = redis_client.get_redis()
    await red.publish(
        f"{AXIOM_EVENTS_PREFIX}{p2}",
        b'{"type":"t","project_id":"x","ts":"s","payload":{"n":1}}',
    )
    r = None
    try:
        r = await ac1.send(
            ac1.build_request(
                "GET",
                f"http://test/v1/events/stream?project_id={p1}",
                headers={**h1, "Accept": "text/event-stream"},
            ),
            stream=True,
        )
        pre = b""
        it0 = r.aiter_bytes()
        for _ in range(30):
            pre += await _bnext(it0)
            if b"event: connected" in pre:
                break
        for _ in range(12):
            chunk = await _bnext(it0)
            assert b'"n":1' not in chunk
    finally:
        if r:
            try:
                await r.aclose()
            except Exception:  # noqa: BLE001
                pass
        await ac1.aclose()


async def test_unauthenticated_401() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/v1/events/stream?project_id={uuid.uuid4()}")
    assert r.status_code == 401


async def test_mismatched_project_id_403() -> None:
    ac, h, _p_ok = await _h_and_pid()
    try:
        r = await ac.get(
            f"http://test/v1/events/stream?project_id={uuid.uuid4()}",
            headers=h,
        )
        assert r.status_code == 403
    finally:
        await ac.aclose()


async def test_invalid_project_uuid_422() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        t = await signup_user(ac, unique_email(), "password1a")
        h = auth_headers(t["access_token"])
        r = await ac.get("/v1/events/stream?project_id=not-a-uuid", headers=h)
    assert r.status_code == 422
