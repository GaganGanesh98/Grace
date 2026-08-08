"""Classify gateway routes into governance intent parameters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from axiom.gateway.provider_registry import get_all_provider_names

_REGISTRY_PROVIDERS = frozenset(get_all_provider_names())


@dataclass(frozen=True)
class GatewayClassification:
    action_type: str
    target: str
    risk: str
    provider: str


def _risk_for_host(host: str) -> str:
    h = host.lower()
    combined = h
    for pattern in ("smtp", "gmail.googleapis.com", "graph.microsoft.com", "slack.com", "hooks.slack.com"):
        if pattern in combined:
            return "high"
    return "medium"


def classify_gateway_request(
    provider: str,
    _method: str,
    _path: str,
    _body: bytes | None,
    *,
    outbound_url: str,
) -> GatewayClassification:
    """Derive governance action_type, risk, and logical target for a gateway hop."""
    p = provider.lower()
    if p in _REGISTRY_PROVIDERS:
        action = f"tool.llm.{p}"
        return GatewayClassification(
            action_type=action,
            target=outbound_url,
            risk="low",
            provider=p,
        )

    if p == "custom":
        parsed = urlparse(outbound_url)
        host = parsed.netloc or ""
        action = "tool.http.custom"
        risk = _risk_for_host(host)
        return GatewayClassification(
            action_type=action,
            target=outbound_url,
            risk=risk,
            provider="custom",
        )

    return GatewayClassification(
        action_type=f"tool.llm.{p}",
        target=outbound_url,
        risk="low",
        provider=p,
    )


def parse_stream_flag(body: bytes | None) -> tuple[bool, dict[str, Any] | None]:
    if not body:
        return False, None
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, None
    if isinstance(data, dict) and data.get("stream") is True:
        return True, data
    return False, data if isinstance(data, dict) else None


def agent_id_from_headers(headers: Any) -> str:
    raw = None
    if hasattr(headers, "get"):
        raw = headers.get("x-axiom-agent-id") or headers.get("X-Axiom-Agent-Id")
    if raw and str(raw).strip():
        return str(raw).strip()[:255]
    return "gateway-agent"
