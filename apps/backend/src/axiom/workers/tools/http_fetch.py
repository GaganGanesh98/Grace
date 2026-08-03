"""HTTP GET fetch tool with mandatory SSRF protection and redirect validation."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import ClassVar
from urllib.parse import urljoin, urlparse

from axiom.core.security import ALLOWED_SCHEMES, BLOCKED_NETWORKS, UnsafeUrlError
from axiom.workers.tools.base import BaseTool, ToolExecutionContext, check_governance

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 10.0
MAX_REDIRECTS = 10


def _blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(ip in net for net in BLOCKED_NETWORKS)


async def assert_safe_fetch_url(url: str) -> None:
    """Resolve hostnames and reject blocked destinations (SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Scheme {parsed.scheme!r} not allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no hostname")

    # Bracketed IPv6 from urlparse
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]

    try:
        ip = ipaddress.ip_address(host)
        if _blocked_ip(ip):
            raise UnsafeUrlError(f"Blocked address: {ip}")
        return
    except ValueError:
        pass

    infos = await asyncio.to_thread(
        socket.getaddrinfo,
        host,
        None,
        socket.AF_UNSPEC,
        socket.SOCK_STREAM,
    )
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _blocked_ip(ip):
            raise UnsafeUrlError(f"Resolved to blocked address: {ip}")


class HttpFetchTool(BaseTool):
    name = "http_fetch"
    description = "Fetch a public HTTP(S) URL (GET only) with SSRF protection."
    schema: ClassVar[dict[str, object]] = {
        "type": "function",
        "function": {
            "name": "http_fetch",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP or HTTPS URL to GET"},
                },
                "required": ["url"],
            },
        },
    }

    async def execute(self, ctx: ToolExecutionContext, **kwargs: object) -> dict[str, object]:
        url = str(kwargs.get("url", "")).strip()
        await check_governance(
            ctx=ctx,
            action_type="tool.http_fetch",
            target=url[:1024],
            parameters={"url": url},
        )
        client = ctx.httpx_client
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            try:
                await assert_safe_fetch_url(current)
            except UnsafeUrlError as exc:
                return {"ok": False, "error": "ssrf_blocked", "detail": str(exc)}
            r = await client.get(current, follow_redirects=False, timeout=FETCH_TIMEOUT_SECONDS)
            if r.status_code in (301, 302, 303, 307, 308):
                loc = r.headers.get("location")
                if not loc:
                    return {
                        "ok": False,
                        "error": "redirect_without_location",
                        "status_code": r.status_code,
                    }
                current = urljoin(str(r.request.url), loc)
                continue
            cl = r.headers.get("content-length")
            if cl is not None:
                try:
                    if int(cl) > MAX_RESPONSE_BYTES:
                        return {"ok": False, "error": "response_too_large"}
                except ValueError:
                    pass
            body = r.content
            if len(body) > MAX_RESPONSE_BYTES:
                return {"ok": False, "error": "response_too_large"}
            text = body.decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status_code": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "body_preview": text[:8192],
            }
        return {"ok": False, "error": "too_many_redirects"}
