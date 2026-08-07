"""Gateway request classification."""

from __future__ import annotations

import pytest

from axiom.gateway.classifier import (
    agent_id_from_headers,
    classify_gateway_request,
)
from axiom.gateway.provider_registry import get_all_provider_names


def test_openai_path_classified_correctly() -> None:
    c = classify_gateway_request(
        "openai",
        "POST",
        "chat/completions",
        b"{}",
        outbound_url="https://api.openai.com/v1/chat/completions",
    )
    assert c.action_type == "tool.llm.openai"
    assert c.provider == "openai"
    assert c.risk == "low"
    assert "openai.com" in c.target


def test_anthropic_path_classified_correctly() -> None:
    c = classify_gateway_request(
        "anthropic",
        "POST",
        "messages",
        b"{}",
        outbound_url="https://api.anthropic.com/v1/messages",
    )
    assert c.action_type == "tool.llm.anthropic"
    assert c.provider == "anthropic"


def test_google_path_classified_correctly() -> None:
    c = classify_gateway_request(
        "google",
        "POST",
        "models",
        b"{}",
        outbound_url="https://generativelanguage.googleapis.com/v1/models",
    )
    assert c.action_type == "tool.llm.google"


def test_generic_proxy_classified_by_method() -> None:
    c = classify_gateway_request(
        "custom",
        "POST",
        "",
        None,
        outbound_url="https://example.com/api",
    )
    assert c.action_type == "tool.http.custom"
    assert c.risk == "medium"


def test_agent_id_from_header() -> None:
    from starlette.datastructures import Headers

    h = Headers({"x-axiom-agent-id": "agent-xyz"})
    assert agent_id_from_headers(h) == "agent-xyz"


def test_agent_id_default_when_missing() -> None:
    assert agent_id_from_headers({}) == "gateway-agent"


def test_risk_low_for_llm_calls() -> None:
    c = classify_gateway_request(
        "groq",
        "POST",
        "x",
        b"{}",
        outbound_url="https://api.groq.com/openai/v1/chat/completions",
    )
    assert c.risk == "low"


def test_risk_medium_for_unknown_post() -> None:
    c = classify_gateway_request(
        "custom",
        "POST",
        "x",
        b"{}",
        outbound_url="https://unknown.example.com/v1/x",
    )
    assert c.risk == "medium"


def test_custom_is_not_a_registry_provider() -> None:
    """The "custom" provider is a generic-proxy sentinel, never a registry entry.

    The registry branch in classify_gateway_request used to carry an
    `and p != "custom"` guard. That guard could never fire: the first condition
    (`p in _REGISTRY_PROVIDERS`) is already false for "custom". This test pins
    the invariant so the dead guard is not reintroduced.
    """
    assert "custom" not in get_all_provider_names()


@pytest.mark.parametrize(
    ("host", "expected_risk"),
    [
        ("hooks.slack.com", "high"),
        ("slack.com", "high"),
        ("gmail.googleapis.com", "high"),
        ("graph.microsoft.com", "high"),
        ("smtp.sendgrid.net", "high"),
        ("example.com", "medium"),
        ("unknown.internal.dev", "medium"),
    ],
)
def test_custom_risk_is_derived_from_host(host: str, expected_risk: str) -> None:
    """Generic-proxy risk varies with the target host, it is not a constant."""
    c = classify_gateway_request(
        "custom",
        "POST",
        "x",
        b"{}",
        outbound_url=f"https://{host}/v1/x",
    )
    assert c.action_type == "tool.http.custom"
    assert c.provider == "custom"
    assert c.risk == expected_risk
