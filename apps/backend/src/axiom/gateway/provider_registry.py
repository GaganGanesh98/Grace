"""
Provider Fabric — Single Source of Truth for all LLM provider configuration.

Every system that needs to know about providers reads from this registry:
- Vault: key prefix → provider identification
- Classifier: provider → intent classification
- Gateway: provider → protocol shape + base URL + auth method

Adding a new provider = adding one entry to PROVIDERS. No new routes, no new
handlers, no code changes anywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ProtocolShape(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    GOOGLE_GEMINI = "google_gemini"


class AuthMethod(StrEnum):
    BEARER = "bearer"  # Authorization: Bearer {key}
    X_API_KEY = "x_api_key"  # x-api-key: {key}  (Anthropic)
    QUERY_PARAM = "query_param"  # ?key={key}  (Google)


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Immutable specification for a single LLM provider."""

    name: str
    key_prefixes: tuple[str, ...]  # longest-first ordering enforced at table build
    protocol: ProtocolShape
    base_url: str
    auth_method: AuthMethod
    default_headers: dict[str, str] = field(default_factory=dict)
    forward_headers: frozenset[str] = frozenset()
    chat_path: str = "/chat/completions"  # relative to base_url (informational)
    supports_streaming: bool = True


# ════════════════════════════════════════════════════════════════════
#  THE REGISTRY — one entry per provider, ordered by match priority
# ════════════════════════════════════════════════════════════════════

PROVIDERS: dict[str, ProviderSpec] = {
    "groq": ProviderSpec(
        name="groq",
        key_prefixes=("gsk_",),
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.groq.com/openai/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "openai": ProviderSpec(
        name="openai",
        key_prefixes=("sk-proj-", "sk-"),  # sk-proj- before sk-
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.openai.com/v1",
        auth_method=AuthMethod.BEARER,
        forward_headers=frozenset({"openai-beta", "openai-organization"}),
    ),
    "anthropic": ProviderSpec(
        name="anthropic",
        key_prefixes=("sk-ant-",),
        protocol=ProtocolShape.ANTHROPIC_MESSAGES,
        base_url="https://api.anthropic.com/v1",
        auth_method=AuthMethod.X_API_KEY,
        default_headers={"anthropic-version": "2023-06-01"},
        forward_headers=frozenset({"anthropic-beta"}),
        chat_path="/messages",
    ),
    "xai": ProviderSpec(
        name="xai",
        key_prefixes=("xai-",),
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.x.ai/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "google": ProviderSpec(
        name="google",
        key_prefixes=("AIza",),
        protocol=ProtocolShape.GOOGLE_GEMINI,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        auth_method=AuthMethod.QUERY_PARAM,
        chat_path="/models/{model}:generateContent",
    ),
    "perplexity": ProviderSpec(
        name="perplexity",
        key_prefixes=("pplx-",),
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.perplexity.ai",
        auth_method=AuthMethod.BEARER,
    ),
    "openrouter": ProviderSpec(
        name="openrouter",
        key_prefixes=("sk-or-",),
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://openrouter.ai/api/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "together": ProviderSpec(
        name="together",
        key_prefixes=(),  # no known prefix — manual provider selection
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.together.xyz/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "fireworks": ProviderSpec(
        name="fireworks",
        key_prefixes=("fp_",),
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.fireworks.ai/inference/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "deepseek": ProviderSpec(
        name="deepseek",
        key_prefixes=("sk-",),  # conflicts with openai — requires manual selection
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.deepseek.com/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "mistral": ProviderSpec(
        name="mistral",
        key_prefixes=(),  # no known unique prefix
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.mistral.ai/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "cerebras": ProviderSpec(
        name="cerebras",
        key_prefixes=("csk-",),
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.cerebras.ai/v1",
        auth_method=AuthMethod.BEARER,
    ),
    "replicate": ProviderSpec(
        name="replicate",
        key_prefixes=("r8_",),
        protocol=ProtocolShape.OPENAI_COMPATIBLE,
        base_url="https://api.replicate.com/v1",
        auth_method=AuthMethod.BEARER,
    ),
}


# ════════════════════════════════════════════════════════════════════
#  LOOKUP FUNCTIONS — used by vault, classifier, and gateway
# ════════════════════════════════════════════════════════════════════


def _prefix_table_entries() -> list[tuple[str, str]]:
    """Build (prefix, provider) pairs; openai must win over deepseek for same-length sk-."""
    entries: list[tuple[str, str]] = []
    for spec in PROVIDERS.values():
        for prefix in spec.key_prefixes:
            entries.append((prefix, spec.name))
    return entries


def _prefix_sort_key(pair: tuple[str, str]) -> tuple[int, int]:
    """Longest prefix first; for equal length, openai wins over deepseek (both may use sk-)."""
    prefix, name = pair
    tie = 0 if name == "openai" else 1 if name == "deepseek" else 2
    return (-len(prefix), tie)


# Pre-computed prefix lookup table (longest-first, then tie-breaker).
_PREFIX_TABLE: list[tuple[str, str]] = sorted(
    _prefix_table_entries(),
    key=_prefix_sort_key,
)


def detect_provider_from_key(api_key: str) -> str | None:
    """
    Detect provider from API key prefix using longest-match-first.

    Returns provider name (e.g., "groq") or None if no prefix matches.
    Used by: vault service when user stores a new key.
    """
    for prefix, provider_name in _PREFIX_TABLE:
        if api_key.startswith(prefix):
            return provider_name
    return None


def get_provider_spec(provider_name: str) -> ProviderSpec | None:
    """
    Get full provider specification by name.

    Used by: gateway proxy handler to determine protocol, URL, auth.
    """
    return PROVIDERS.get(provider_name.lower())


def get_all_provider_names() -> list[str]:
    """Return all registered provider names. Used by: classifier, UI dropdowns."""
    return list(PROVIDERS.keys())


def get_providers_by_protocol(protocol: ProtocolShape) -> list[ProviderSpec]:
    """Return all providers using a given protocol shape."""
    return [spec for spec in PROVIDERS.values() if spec.protocol == protocol]
