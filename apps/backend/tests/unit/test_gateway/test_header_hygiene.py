"""RFC 7230 §6.1 header hygiene tests for merge_forward_headers."""

from __future__ import annotations

import pytest

from axiom.gateway.protocol_handlers import (
    GATEWAY_USER_AGENT,
    merge_forward_headers,
    prepare_upstream_request,
)
from axiom.gateway.provider_registry import PROVIDERS


def _lower_keys(d: dict[str, str]) -> dict[str, str]:
    return {k.lower(): v for k, v in d.items()}


class TestHostNeverLeaks:
    """Inbound Host (any casing) must never appear in outbound headers."""

    @pytest.mark.parametrize("host_key", ["Host", "host", "HOST"])
    def test_host_never_leaks(self, host_key: str) -> None:
        inbound = {
            host_key: "localhost:8001",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        lower = _lower_keys(out)
        assert "host" not in lower


class TestHopByHopStripped:
    """All 8 RFC 7230 §6.1 hop-by-hop headers must be stripped."""

    HOP_BY_HOP = [
        "Connection",
        "Keep-Alive",
        "Proxy-Authenticate",
        "Proxy-Authorization",
        "TE",
        "Trailer",
        "Transfer-Encoding",
        "Upgrade",
    ]

    @pytest.mark.parametrize("header", HOP_BY_HOP)
    def test_hop_by_hop_stripped(self, header: str) -> None:
        inbound = {
            header: "some-value",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        lower = _lower_keys(out)
        assert header.lower() not in lower


class TestContentLengthNotForwarded:
    """Content-Length must not be forwarded — httpx recomputes it from body."""

    def test_content_length_not_forwarded(self) -> None:
        inbound = {
            "Content-Length": "42",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        lower = _lower_keys(out)
        assert "content-length" not in lower


class TestUserAgentIsAxiom:
    """Outbound User-Agent must be the gateway's own, not the client's."""

    def test_user_agent_is_axiom(self) -> None:
        inbound = {
            "User-Agent": "python-httpx/0.27.0",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        assert out["User-Agent"].startswith("axiom-gateway/")
        assert out["User-Agent"] == GATEWAY_USER_AGENT

    def test_user_agent_set_even_when_absent(self) -> None:
        out = merge_forward_headers({"Content-Type": "application/json"})
        assert out["User-Agent"] == GATEWAY_USER_AGENT


class TestConnectionHeaderTokens:
    """Headers named in Connection's token list are also stripped."""

    def test_connection_token_headers_stripped(self) -> None:
        inbound = {
            "Connection": "X-Custom-Hop, keep-alive",
            "X-Custom-Hop": "secret",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        lower = _lower_keys(out)
        assert "x-custom-hop" not in lower
        assert "connection" not in lower


class TestAxiomAndForwardedStripped:
    """Internal x-axiom-* and x-forwarded-* headers never leak upstream."""

    def test_axiom_headers_stripped(self) -> None:
        inbound = {
            "x-axiom-trace": "abc",
            "x-axiom-project-id": "123",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        assert not any(k.lower().startswith("x-axiom") for k in out)

    def test_forwarded_headers_stripped(self) -> None:
        inbound = {
            "x-forwarded-for": "1.2.3.4",
            "x-forwarded-proto": "https",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        assert not any(k.lower().startswith("x-forwarded") for k in out)


class TestAuthorizationStripped:
    """Inbound Authorization and x-api-key are never forwarded."""

    def test_authorization_stripped(self) -> None:
        inbound = {
            "Authorization": "Bearer client-token",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        lower = _lower_keys(out)
        assert "authorization" not in lower

    def test_x_api_key_stripped(self) -> None:
        inbound = {
            "x-api-key": "client-key",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        lower = _lower_keys(out)
        assert "x-api-key" not in lower


class TestSafeEndToEnd:
    """Content-Type and Accept are forwarded as safe end-to-end headers."""

    def test_content_type_forwarded(self) -> None:
        out = merge_forward_headers({"Content-Type": "application/json"})
        assert out["Content-Type"] == "application/json"

    def test_accept_forwarded(self) -> None:
        out = merge_forward_headers({"Accept": "text/event-stream"})
        assert out["Accept"] == "text/event-stream"

    def test_prepare_upstream_request_does_not_duplicate_lowercase_content_type(self) -> None:
        spec = PROVIDERS["openai"]
        headers, _ = prepare_upstream_request(
            spec,
            "sk-test",
            "https://api.openai.com/v1/chat/completions",
            {"content-type": "application/json"},
        )

        assert sum(1 for key in headers if key.lower() == "content-type") == 1
        assert headers["content-type"] == "application/json"


class TestProviderForwardHeaders:
    """Provider-specific headers pass through when whitelisted."""

    def test_whitelisted_provider_header_forwarded(self) -> None:
        inbound = {
            "openai-beta": "assistants=v2",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(
            inbound, provider_forward_headers=frozenset({"openai-beta"}),
        )
        assert out["openai-beta"] == "assistants=v2"

    def test_non_whitelisted_provider_header_dropped(self) -> None:
        inbound = {
            "openai-beta": "assistants=v2",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        assert "openai-beta" not in out


class TestAcceptEncodingStripped:
    """Accept-Encoding must not be forwarded — let httpx negotiate."""

    def test_accept_encoding_stripped(self) -> None:
        inbound = {
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json",
        }
        out = merge_forward_headers(inbound)
        lower = _lower_keys(out)
        assert "accept-encoding" not in lower
