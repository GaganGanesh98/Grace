"""Response-side RFC 7230 header hygiene for upstream responses."""

from __future__ import annotations

import httpx
import pytest

from axiom.gateway.protocol_handlers import (
    _RESPONSE_NEVER_FORWARD,
    sanitize_upstream_response_headers,
)


class TestContentEncodingStripped:

    def test_content_encoding_stripped(self) -> None:
        h = httpx.Headers({"content-encoding": "gzip", "content-type": "application/json"})
        out = sanitize_upstream_response_headers(h)
        assert "content-encoding" not in {k.lower() for k in out}
        assert out["content-type"] == "application/json"


class TestHopByHopStrippedFromResponse:

    HOP_BY_HOP = [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    ]

    @pytest.mark.parametrize("header", HOP_BY_HOP)
    def test_hop_by_hop_stripped(self, header: str) -> None:
        h = httpx.Headers({header: "some-value", "content-type": "application/json"})
        out = sanitize_upstream_response_headers(h)
        assert header.lower() not in {k.lower() for k in out}


class TestSafeHeadersPassThrough:

    @pytest.mark.parametrize(
        "header,value",
        [
            ("content-type", "application/json"),
            ("x-request-id", "abc-123"),
            ("x-axiom-receipt-id", "r-456"),
        ],
    )
    def test_safe_headers_pass_through(self, header: str, value: str) -> None:
        h = httpx.Headers({header: value})
        out = sanitize_upstream_response_headers(h)
        lower_out = {k.lower(): v for k, v in out.items()}
        assert lower_out[header.lower()] == value


class TestCaseInsensitiveStrip:

    @pytest.mark.parametrize("casing", ["content-encoding", "Content-Encoding", "CONTENT-ENCODING"])
    def test_case_insensitive_strip(self, casing: str) -> None:
        h = httpx.Headers({casing: "gzip", "x-request-id": "ok"})
        out = sanitize_upstream_response_headers(h)
        assert "content-encoding" not in {k.lower() for k in out}
        lower_out = {k.lower(): v for k, v in out.items()}
        assert lower_out["x-request-id"] == "ok"
