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


def _bare_model(model: str, provider: str) -> str:
    """Drop a leading ``<provider>/`` the same way the gateway does on the body.

    Agent definitions store models as ``<provider>/<model>``; Google needs the
    bare id inside the URL path. Only the first segment is removed, because ids
    such as ``openai/gpt-oss-120b`` are themselves slash-bearing.
    """
    prefix, sep, rest = model.partition("/")
    if sep and rest and prefix.lower() == provider.lower():
        return rest
    return model


def gateway_llm_post_path(provider: str, model: str | None = None) -> str:
    """Return the path segment after ``/v1/{provider}/`` for a completion request.

    Google addresses the model in the URL rather than the body
    (``ProviderSpec.chat_path`` carries the ``{model}`` placeholder), so the
    caller's model has to be threaded through. It previously hardcoded
    ``gemini-pro``, which meant every Google agent silently ran on that model
    whatever its definition said.
    """

    p = provider.lower()
    spec = get_provider_spec(p)
    if spec is None:
        msg = f"Unknown LLM provider {provider!r}; not in provider registry"
        raise ValueError(msg)

    if "{model}" in spec.chat_path:
        resolved = _bare_model((model or "").strip(), p) or spec.default_model
        if not resolved:
            msg = f"Provider {provider!r} addresses the model in the URL; a model is required"
            raise ValueError(msg)
        return spec.chat_path.strip("/").format(model=resolved)

    return spec.chat_path.strip("/")


def gateway_llm_url(provider: str, model: str | None = None) -> str:
    """Full URL for POST (OpenAI-compatible or provider-specific via gateway routes)."""

    base = gateway_base_http().rstrip("/")
    sub = gateway_llm_post_path(provider, model).strip("/")
    return f"{base}/v1/{provider.lower()}/{sub}"
