"""Build governance-gateway paths (localhost only — no upstream provider URLs in worker code)."""

from __future__ import annotations

from axiom.config import get_settings
from axiom.gateway.provider_registry import get_provider_spec


def gateway_base_http() -> str:
    """HTTP base for the governance gateway process (default port 8001)."""

    port = get_settings().gateway_port
    # Default deployment: http://localhost:8001 — only outbound HTTP target for workers.
    if port == 8001:
        return "http://localhost:8001"
    return f"http://localhost:{port}"


def gateway_llm_post_path(provider: str) -> str:
    """Return the path segment after ``/v1/{provider}/`` for a completion request."""

    p = provider.lower()
    if get_provider_spec(p) is None:
        msg = f"Unknown LLM provider {provider!r}; not in provider registry"
        raise ValueError(msg)
    if p == "anthropic":
        return "messages"
    if p == "google":
        return "models/gemini-pro:generateContent"
    return "chat/completions"


def gateway_llm_url(provider: str) -> str:
    """Full URL for POST (OpenAI-compatible or provider-specific via gateway routes)."""

    base = gateway_base_http().rstrip("/")
    sub = gateway_llm_post_path(provider).strip("/")
    return f"{base}/v1/{provider.lower()}/{sub}"
