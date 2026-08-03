"""HTTP proxy helpers."""

from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

from axiom.gateway.proxy import (
    assert_public_http_url,
    filter_response_headers,
    open_streaming_response,
    proxy_request,
)


@pytest.mark.asyncio
async def test_proxy_forwards_request_to_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        r = await proxy_request(
            client,
            "POST",
            "https://example.com/v1/x",
            {"content-type": "application/json"},
            b'{"a":1}',
            timeout=5.0,
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_proxy_returns_provider_response() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(201, content=b"created"))
    async with httpx.AsyncClient(transport=transport) as client:
        r = await proxy_request(client, "POST", "https://example.com", {}, b"x")
    assert r.status_code == 201
    assert r.content == b"created"


@pytest.mark.asyncio
async def test_proxy_handles_provider_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(502, content=b"bad"))
    async with httpx.AsyncClient(transport=transport) as client:
        r = await proxy_request(client, "GET", "https://example.com", {}, None)
    assert r.status_code == 502


def test_ssrf_rejects_non_http_scheme() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_public_http_url("ftp://example.com/file")
    assert exc.value.status_code == 400


def test_proxy_strips_axiom_headers() -> None:
    h = httpx.Headers(
        [
            ("content-type", "application/json"),
            ("transfer-encoding", "chunked"),
            ("connection", "keep-alive"),
        ]
    )
    out = filter_response_headers(h)
    assert "connection" not in {k.lower() for k in out}
    assert out.get("content-type") == "application/json"


@pytest.mark.asyncio
async def test_streaming_response_forwards_chunks() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"xy"))
    async with httpx.AsyncClient(transport=transport) as client:
        resp, aiter = await open_streaming_response(
            client,
            "GET",
            "https://example.com/stream",
            {},
            None,
            timeout=5.0,
        )
        assert resp.status_code == 200
        got = []
        async for part in aiter:
            got.append(part)
    assert got == [b"xy"]


def test_ssrf_blocks_loopback() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_public_http_url("http://127.0.0.1:8080/")
    assert exc.value.status_code == 403
