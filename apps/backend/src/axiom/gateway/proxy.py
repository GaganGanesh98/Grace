"""HTTP forwarding with optional SSE streaming + SSRF guards."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import httpx
import structlog
from fastapi import HTTPException

logger = structlog.get_logger(__name__)


def assert_public_http_url(url: str) -> None:
    """Reject private / link-local / loopback destinations (generic proxy SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_url", "message": "Only http(s) URLs are allowed"},
        )
    host = parsed.hostname
    if not host:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_url", "message": "Missing host"},
        )

    if host == "localhost" or host.endswith(".localhost"):
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden_host", "message": "Local targets are blocked"},
        )

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "dns_error", "message": "Could not resolve host"},
        ) from exc

    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden_host", "message": "Private IPs are blocked"},
            )


async def proxy_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    timeout: float = 120.0,
) -> httpx.Response:
    parsed = urlparse(url)
    logger.info(
        "gateway.proxy.send",
        method=method,
        upstream_host=parsed.hostname,
        upstream_path=parsed.path,
        body_bytes=len(body) if body else 0,
        has_authorization=bool(headers.get("Authorization") or headers.get("authorization")),
        has_x_api_key=bool(headers.get("x-api-key")),
    )
    logger.info(
        "gateway.proxy.outbound_headers",
        header_names=sorted(headers.keys()),
        host_header=headers.get("host") or headers.get("Host"),
        user_agent=headers.get("user-agent") or headers.get("User-Agent"),
        content_length=headers.get("content-length") or headers.get("Content-Length"),
    )
    response = await client.request(
        method=method,
        url=url,
        headers=headers,
        content=body,
        timeout=timeout,
    )
    logger.info(
        "gateway.proxy.response",
        upstream_host=parsed.hostname,
        upstream_path=parsed.path,
        status=response.status_code,
    )
    return response


async def open_streaming_response(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    timeout: float = 120.0,
) -> tuple[httpx.Response, AsyncGenerator[bytes, None]]:
    """Return the httpx Response plus a byte iterator (closes stream when exhausted)."""
    ctx = client.stream(
        method=method,
        url=url,
        headers=headers,
        content=body,
        timeout=timeout,
    )
    response = await ctx.__aenter__()

    async def chunks() -> AsyncGenerator[bytes, None]:
        try:
            async for part in response.aiter_bytes():
                yield part
        finally:
            await ctx.__aexit__(None, None, None)

    return response, chunks()


def filter_response_headers(h: httpx.Headers) -> dict[str, str]:
    """Drop hop-by-hop headers when building the client response."""
    drop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
    out: dict[str, str] = {}
    for key, value in h.multi_items():
        if key.lower() in drop:
            continue
        out[key] = value
    return out
