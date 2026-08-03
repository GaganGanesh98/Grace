"""
Three protocol handlers (OpenAI-compatible, Anthropic Messages, Google Gemini) plus dispatch.

All outbound LLM proxying uses these helpers so auth and URL construction stay consistent
with the provider registry.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from axiom.gateway.provider_registry import (
    AuthMethod,
    ProtocolShape,
    ProviderSpec,
    get_all_provider_names,
    get_provider_spec,
)

_norm_logger = logging.getLogger(__name__)


def normalize_model_prefix(body: bytes, provider: str) -> bytes:
    """Strip ``<provider>/`` prefix from the ``model`` field in a JSON body.

    Returns the original bytes unchanged when no rewrite is needed.
    """
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body

    if not isinstance(parsed, dict):
        return body

    model = parsed.get("model")
    if not isinstance(model, str) or "/" not in model:
        return body

    prefix, _, bare = model.partition("/")
    if not bare:
        return body

    if prefix.lower() != provider.lower():
        _norm_logger.warning(
            "gateway.model_prefix_mismatch: body has '%s/' prefix but provider is '%s'; stripping anyway",
            prefix,
            provider,
        )

    parsed["model"] = bare
    return json.dumps(parsed, separators=(",", ":")).encode()


def build_upstream_url(spec: ProviderSpec, path_suffix: str) -> str:
    """Join registry base URL with the gateway path suffix (e.g. chat/completions)."""
    base = spec.base_url.rstrip("/")
    sub = path_suffix.lstrip("/")
    return f"{base}/{sub}" if sub else base


_HOP_BY_HOP = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
})

_NEVER_FORWARD = frozenset({
    "host",
    "content-length",
    "accept-encoding",
    "authorization",
    "x-api-key",
    "x-correlation-id",
    "user-agent",
})

_SAFE_END_TO_END = frozenset({
    "content-type",
    "accept",
})

GATEWAY_USER_AGENT = "axiom-gateway/1.0"

_RESPONSE_NEVER_FORWARD = frozenset({
    "content-encoding",
    "content-length",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
})


def sanitize_upstream_response_headers(
    upstream_headers: httpx.Headers,
) -> dict[str, str]:
    """Strip hop-by-hop and content-encoding headers from upstream responses.

    httpx transparently decompresses response bodies, so forwarding the
    original Content-Encoding causes the caller to attempt a second
    decompression on already-plain bytes.
    """
    out: dict[str, str] = {}
    for key, value in upstream_headers.multi_items():
        if key.lower() in _RESPONSE_NEVER_FORWARD:
            continue
        out[key] = value
    return out


def merge_forward_headers(
    request_headers: dict[str, str],
    *,
    provider_forward_headers: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Build outbound headers from scratch per RFC 7230 section 6.1.

    Only copies safe end-to-end headers and provider-specific whitelisted
    headers. Everything else is dropped — httpx sets Host, Content-Length,
    and compression negotiation from the actual request.
    """
    connection_tokens: set[str] = set()
    for k, v in request_headers.items():
        if k.lower() == "connection":
            connection_tokens = {t.strip().lower() for t in v.split(",")}
            break

    allowed = _SAFE_END_TO_END | provider_forward_headers
    outbound: dict[str, str] = {}

    for k, v in request_headers.items():
        lower = k.lower()
        if lower in _HOP_BY_HOP:
            continue
        if lower in _NEVER_FORWARD:
            continue
        if lower in connection_tokens:
            continue
        if lower.startswith(("x-axiom-", "x-forwarded-")):
            continue
        if lower in allowed:
            outbound[k] = v

    outbound["User-Agent"] = GATEWAY_USER_AGENT
    return outbound


def prepare_upstream_request(
    spec: ProviderSpec,
    decrypted_key: str,
    outbound_url: str,
    forwarded_headers: dict[str, str],
) -> tuple[dict[str, str], str]:
    """
    Build outbound headers and URL (query-param auth for Google).

    ``forwarded_headers`` must already be sanitised via :func:`merge_forward_headers`.

    Raises:
        ValueError: if auth_method is not supported.
    """
    outbound = dict(forwarded_headers)
    modified_url = outbound_url

    if spec.auth_method == AuthMethod.QUERY_PARAM:
        parsed = urlparse(outbound_url)
        q = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "key"]
        q.append(("key", decrypted_key))
        new_q = urlencode(q)
        modified_url = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment)
        )
    elif spec.auth_method == AuthMethod.BEARER:
        outbound["Authorization"] = f"Bearer {decrypted_key}"
    elif spec.auth_method == AuthMethod.X_API_KEY:
        outbound["x-api-key"] = decrypted_key
    else:
        msg = f"Unsupported auth method: {spec.auth_method}"
        raise ValueError(msg)

    if not any(k.lower() == "content-type" for k in outbound):
        outbound["Content-Type"] = "application/json"

    for ek, ev in spec.default_headers.items():
        outbound[ek] = ev

    return outbound, modified_url


async def proxy_openai_compatible(
    spec: ProviderSpec,
    decrypted_key: str,
    body: bytes,
    path_suffix: str,
    http_client: httpx.AsyncClient,
    *,
    forward_headers: dict[str, str] | None = None,
) -> httpx.Response:
    """
    Forward request to any OpenAI-compatible provider.

    Covers: OpenAI, Groq, xAI, Together, Fireworks, Perplexity,
            DeepSeek, Mistral, Cerebras, OpenRouter, and future providers.
    """
    if spec.protocol != ProtocolShape.OPENAI_COMPATIBLE:
        msg = f"Expected openai_compatible protocol, got {spec.protocol}"
        raise ValueError(msg)
    url = build_upstream_url(spec, path_suffix)
    merged = merge_forward_headers(
        forward_headers or {}, provider_forward_headers=spec.forward_headers,
    )
    out_headers, out_url = prepare_upstream_request(spec, decrypted_key, url, merged)
    return await http_client.post(out_url, content=body, headers=out_headers, timeout=120.0)


async def proxy_anthropic_messages(
    spec: ProviderSpec,
    decrypted_key: str,
    body: bytes,
    path_suffix: str,
    http_client: httpx.AsyncClient,
    *,
    forward_headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Forward request to Anthropic Messages API (x-api-key + anthropic-version)."""
    if spec.protocol != ProtocolShape.ANTHROPIC_MESSAGES:
        msg = f"Expected anthropic_messages protocol, got {spec.protocol}"
        raise ValueError(msg)
    url = build_upstream_url(spec, path_suffix)
    merged = merge_forward_headers(
        forward_headers or {}, provider_forward_headers=spec.forward_headers,
    )
    out_headers, out_url = prepare_upstream_request(spec, decrypted_key, url, merged)
    return await http_client.post(out_url, content=body, headers=out_headers, timeout=120.0)


async def proxy_google_gemini(
    spec: ProviderSpec,
    decrypted_key: str,
    body: bytes,
    path_suffix: str,
    http_client: httpx.AsyncClient,
    *,
    forward_headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Forward request to Google Gemini (API key as ?key= only, not in headers)."""
    if spec.protocol != ProtocolShape.GOOGLE_GEMINI:
        msg = f"Expected google_gemini protocol, got {spec.protocol}"
        raise ValueError(msg)
    url = build_upstream_url(spec, path_suffix)
    merged = merge_forward_headers(
        forward_headers or {}, provider_forward_headers=spec.forward_headers,
    )
    out_headers, out_url = prepare_upstream_request(spec, decrypted_key, url, merged)
    return await http_client.post(out_url, content=body, headers=out_headers, timeout=120.0)


PROTOCOL_HANDLERS = {
    ProtocolShape.OPENAI_COMPATIBLE: proxy_openai_compatible,
    ProtocolShape.ANTHROPIC_MESSAGES: proxy_anthropic_messages,
    ProtocolShape.GOOGLE_GEMINI: proxy_google_gemini,
}


async def dispatch_to_provider(
    provider_name: str,
    decrypted_key: str,
    body: bytes,
    path_suffix: str,
    http_client: httpx.AsyncClient,
    *,
    forward_headers: dict[str, str] | None = None,
) -> httpx.Response:
    """
    Look up provider in registry, select protocol handler, forward request.

    Raises:
        ValueError: if provider_name is unknown or protocol has no handler.
    """
    spec = get_provider_spec(provider_name)
    if spec is None:
        known = ", ".join(get_all_provider_names())
        raise ValueError(f"Unknown provider: {provider_name!r}. Known providers: {known}")

    handler = PROTOCOL_HANDLERS.get(spec.protocol)
    if handler is None:
        raise ValueError(f"No protocol handler for {spec.protocol}")

    return await handler(
        spec,
        decrypted_key,
        body,
        path_suffix,
        http_client,
        forward_headers=forward_headers,
    )
