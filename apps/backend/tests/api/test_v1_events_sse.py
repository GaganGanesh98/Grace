"""Phase 7.6 — /v1/events/stream SSE (Redis pub/sub).

These tests need a real socket, not ASGITransport.

``httpx.ASGITransport.handle_async_request`` does ``await self.app(...)`` to
completion and only then wraps the collected ``body_parts`` list in a response
— so ``stream=True`` buys nothing, and against an endpoint whose generator is
``while True`` the send never returns at all. Every streaming test here used to
hang inside ``ac.send()``, before its first assertion, wedging the whole pytest
process and leaving the request's database session open (visible in Postgres as
``idle in transaction``). So the streaming tests run against an in-process
uvicorn server on an ephemeral port, which delivers chunks as they are yielded.

In-process matters: the ``heartbeat_2s`` fixture mutates the environment and
clears the ``get_settings`` cache that the route reads per request, and both
sides share module globals.

The three tests that never reach the stream — 401, 403, 422 — keep using
ASGITransport, where the response completes normally.

Every read is bounded. A live stream can still stall, and an unbounded await on
one is a hang rather than a failure.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator

import orjson
import pytest
import pytest_asyncio
import uvicorn
from httpx import ASGITransport, AsyncClient, Response, Timeout

from axiom.config import get_settings
from axiom.main import app
from axiom.services import redis_client
from axiom.services.events.publisher import AXIOM_EVENTS_PREFIX, publish_axiom_event
from tests.conftest import auth_headers, signup_user, unique_email, unique_slug

pytestmark = pytest.mark.asyncio

# A chunk the server means to send arrives in milliseconds. Beyond this it is a
# stall, not slowness — fail loudly rather than block the suite.
_READ_TIMEOUT = 10.0
# Ceiling for a whole accumulation loop; generous for several 2s heartbeats.
_LOOP_TIMEOUT = 30.0
_SERVER_BOOT_TIMEOUT = 30.0


# ── live server ────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def live_url() -> AsyncIterator[str]:
    """Serve the app on an ephemeral port for the duration of the session."""
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    deadline = time.monotonic() + _SERVER_BOOT_TIMEOUT
    while not server.started:
        if task.done():
            task.result()  # re-raise whatever killed startup
            raise RuntimeError("uvicorn exited during startup")
        if time.monotonic() > deadline:
            task.cancel()
            raise RuntimeError(f"uvicorn did not start within {_SERVER_BOOT_TIMEOUT}s")
        await asyncio.sleep(0.05)

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=15)
        except (TimeoutError, asyncio.CancelledError):
            server.force_exit = True
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


# ── bounded reads ──────────────────────────────────────────────────────────────


async def _bnext(ait: AsyncIterator[bytes], timeout: float = _READ_TIMEOUT) -> bytes:
    """Next chunk, or fail the test — never block indefinitely."""
    try:
        return await asyncio.wait_for(ait.__anext__(), timeout)
    except TimeoutError as exc:
        raise AssertionError(f"SSE stream produced no chunk within {timeout}s") from exc


async def _bnext_or_none(ait: AsyncIterator[bytes], timeout: float) -> bytes | None:
    """Next chunk, or ``None`` if the stream stays quiet — silence is not failure."""
    try:
        return await asyncio.wait_for(ait.__anext__(), timeout)
    except (TimeoutError, StopAsyncIteration):
        return None


async def _read_until(
    ait: AsyncIterator[bytes],
    predicate: Callable[[bytes], bool],
    *,
    timeout: float = _LOOP_TIMEOUT,
    what: str = "expected data",
) -> bytes:
    """Accumulate chunks until ``predicate(buf)`` holds, bounded by wall-clock."""
    buf = b""
    deadline = time.monotonic() + timeout
    while not predicate(buf):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"timed out after {timeout}s waiting for {what}; got: {buf!r}")
        buf += await _bnext(ait, min(_READ_TIMEOUT, remaining))
    return buf


# ── heartbeat ──────────────────────────────────────────────────────────────────


@pytest.fixture
def heartbeat_2s() -> Iterator[None]:
    """Shorten the heartbeat.

    At the 20s default, a test waiting on heartbeat-driven chunks takes minutes,
    which is indistinguishable from a hang. Every streaming test needs this.
    """
    os.environ["GRACE_EVENTS_HEARTBEAT_SECONDS"] = "2"
    get_settings.cache_clear()
    yield
    os.environ.pop("GRACE_EVENTS_HEARTBEAT_SECONDS", None)
    get_settings.cache_clear()


# ── clients ────────────────────────────────────────────────────────────────────


async def _h_and_pid(base_url: str | None = None) -> tuple[AsyncClient, dict[str, str], str]:
    """A signed-up client and one project it owns.

    ``base_url`` selects a real socket; omit it for the in-memory transport.
    """
    if base_url is None:
        ac = AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        )
    else:
        # read=None: this client reads an endless stream, and the per-read bound
        # belongs in _bnext where the failure message can say what was expected.
        ac = AsyncClient(base_url=base_url, timeout=Timeout(10.0, read=None))

    tokens = await signup_user(ac, unique_email(), "password1a")
    h = auth_headers(tokens["access_token"])
    p = await ac.post(
        "/api/v1/projects", headers=h, json={"name": "E", "slug": unique_slug("e-proj")}
    )
    assert p.status_code == 201, p.text
    return ac, h, p.json()["data"]["id"]


@contextlib.asynccontextmanager
async def _stream(ac: AsyncClient, h: dict[str, str], pid: str) -> AsyncIterator[Response]:
    """Open the SSE response and guarantee it is closed.

    Closing is what disconnects the client and lets the server-side generator
    unwind; leaving it open strands the request and its database session.
    """
    r = await ac.send(
        ac.build_request(
            "GET",
            f"/v1/events/stream?project_id={pid}",
            headers={**h, "Accept": "text/event-stream"},
        ),
        stream=True,
    )
    try:
        yield r
    finally:
        with contextlib.suppress(Exception):
            await r.aclose()


# ── streaming tests ────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("heartbeat_2s")
async def test_sse_stream_headers_and_initial_connected(live_url: str) -> None:
    ac, h, pid = await _h_and_pid(live_url)
    try:
        async with _stream(ac, h, pid) as r:
            assert r.status_code == 200
            ctype = (r.headers.get("content-type") or "").split(";")[0].strip()
            assert ctype == "text/event-stream"
            assert "no-cache" in (r.headers.get("cache-control") or "").lower()
            assert (r.headers.get("x-accel-buffering") or "") == "no"

            buf = await _read_until(
                r.aiter_bytes(),
                lambda b: b"event: connected" in b and b"stream_id" in b,
                what="the connected event",
            )
            m = b""
            for line in buf.split(b"\n"):
                if line.startswith(b"data: "):
                    m = line[6:].strip()
            assert m, buf
            d = orjson.loads(m)
            assert d.get("stream_id")
            assert d.get("server_time")
    finally:
        await ac.aclose()


@pytest.mark.usefixtures("heartbeat_2s")
async def test_heartbeat_multiple_pings(live_url: str) -> None:
    ac, h, pid = await _h_and_pid(live_url)
    try:
        async with _stream(ac, h, pid) as r:
            assert r.status_code == 200
            buf = await _read_until(
                r.aiter_bytes(),
                lambda b: b.count(b"event: ping") >= 3,
                what="three heartbeat pings",
            )
            assert buf.count(b"event: ping") >= 3
    finally:
        await ac.aclose()


@pytest.mark.usefixtures("heartbeat_2s")
async def test_subscriber_receives_same_project_event(live_url: str) -> None:
    ac, h, pid = await _h_and_pid(live_url)
    try:
        async with _stream(ac, h, pid) as r:
            assert r.status_code == 200
            it0 = r.aiter_bytes()
            # The subscription is only live once `connected` has been emitted;
            # publishing earlier races the subscribe and the message is dropped.
            await _read_until(it0, lambda b: b"event: connected" in b, what="the connected event")

            rid = str(uuid.uuid4())
            await publish_axiom_event(
                "receipt.sealed",
                uuid.UUID(str(pid)),
                {"receipt_id": rid, "verdict": "DENY", "agent_id": str(uuid.uuid4())},
            )
            more = await _read_until(
                it0,
                lambda b: rid.encode() in b and b"event: receipt.sealed" in b,
                what="the published receipt.sealed event",
            )
            assert b"event: receipt.sealed" in more
            assert rid.encode() in more
    finally:
        await ac.aclose()


@pytest.mark.usefixtures("heartbeat_2s")
async def test_does_not_receive_different_project_channel(live_url: str) -> None:
    ac1, h1, p1 = await _h_and_pid(live_url)
    p2 = str(uuid.uuid4())
    try:
        async with _stream(ac1, h1, p1) as r:
            assert r.status_code == 200
            it0 = r.aiter_bytes()
            # Publish only once `connected` has arrived. Redis pub/sub is
            # fire-and-forget, so a message sent before the subscribe lands is
            # dropped for every channel alike — publishing first would let this
            # pass even with no project filtering at all.
            await _read_until(it0, lambda b: b"event: connected" in b, what="the connected event")

            red = redis_client.get_redis()
            await red.publish(
                f"{AXIOM_EVENTS_PREFIX}{p2}",
                b'{"type":"t","project_id":"x","ts":"s","payload":{"n":1}}',
            )

            # Drain a fixed window: the heartbeats prove the stream is alive, and
            # the other project's payload must never appear on it.
            deadline = time.monotonic() + 6.0
            saw_ping = False
            while time.monotonic() < deadline:
                chunk = await _bnext_or_none(it0, min(2.0, deadline - time.monotonic()))
                if chunk is None:
                    continue
                assert b'"n":1' not in chunk, "event leaked across project channels"
                saw_ping = saw_ping or b"event: ping" in chunk
            assert saw_ping, "stream went silent — the drain window proved nothing"
    finally:
        await ac1.aclose()


# ── rejected before streaming begins ───────────────────────────────────────────


async def test_unauthenticated_401() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/v1/events/stream?project_id={uuid.uuid4()}")
    assert r.status_code == 401


async def test_mismatched_project_id_403() -> None:
    ac, h, _p_ok = await _h_and_pid()
    try:
        r = await ac.get(f"/v1/events/stream?project_id={uuid.uuid4()}", headers=h)
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
