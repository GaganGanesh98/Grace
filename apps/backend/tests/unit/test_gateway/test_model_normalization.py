"""Tests for provider-prefix normalization of the model field in request bodies."""

from __future__ import annotations

import hashlib
import json
import logging

import pytest

from axiom.gateway.protocol_handlers import normalize_model_prefix
from axiom.gateway.upstream_audit import sha256_hex


class TestNormalizeModelPrefix:

    def test_strips_matching_provider_prefix(self) -> None:
        body = json.dumps({"model": "groq/llama-3.3-70b-versatile", "messages": []}).encode()
        result = normalize_model_prefix(body, "groq")
        parsed = json.loads(result)
        assert parsed["model"] == "llama-3.3-70b-versatile"
        assert parsed["messages"] == []

    def test_strips_mismatched_provider_prefix_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        body = json.dumps({"model": "openai/gpt-4", "messages": []}).encode()
        with caplog.at_level(logging.WARNING):
            result = normalize_model_prefix(body, "groq")
        parsed = json.loads(result)
        assert parsed["model"] == "gpt-4"
        assert "mismatch" in caplog.text.lower()

    def test_bare_model_passes_through(self) -> None:
        body = json.dumps({"model": "llama-3.3-70b-versatile", "messages": []}).encode()
        result = normalize_model_prefix(body, "groq")
        assert result is body

    def test_no_model_field_passes_through(self) -> None:
        body = json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode()
        result = normalize_model_prefix(body, "groq")
        assert result is body

    def test_non_json_body_passes_through(self) -> None:
        body = b"raw bytes that are not json"
        result = normalize_model_prefix(body, "groq")
        assert result is body

    def test_request_hash_is_of_original_body(self) -> None:
        original = json.dumps({"model": "groq/llama-3.3-70b-versatile", "messages": []}).encode()
        normalized = normalize_model_prefix(original, "groq")
        assert normalized != original
        audit_hash = sha256_hex(original)
        assert audit_hash == hashlib.sha256(original).hexdigest()
        assert audit_hash != hashlib.sha256(normalized).hexdigest()
