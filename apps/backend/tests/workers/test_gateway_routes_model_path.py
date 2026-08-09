"""Gateway path building — the model must reach providers that address it in the URL."""

from __future__ import annotations

import pytest

from axiom.gateway.provider_registry import get_provider_spec
from axiom.workers.gateway_routes import gateway_llm_post_path, gateway_llm_url


class TestGooglePathCarriesTheModel:
    """Regression: this returned a hardcoded `gemini-pro` for every Google agent."""

    def test_uses_the_requested_model(self) -> None:
        assert (
            gateway_llm_post_path("google", "google/gemini-2.5-pro")
            == "models/gemini-2.5-pro:generateContent"
        )

    def test_accepts_a_bare_model_id(self) -> None:
        assert (
            gateway_llm_post_path("google", "gemini-3.5-flash")
            == "models/gemini-3.5-flash:generateContent"
        )

    def test_never_hardcodes_gemini_pro(self) -> None:
        path = gateway_llm_post_path("google", "google/gemini-2.5-flash-lite")
        assert "gemini-pro" not in path

    def test_falls_back_to_the_registry_default_when_no_model_is_given(self) -> None:
        spec = get_provider_spec("google")
        assert spec is not None
        assert gateway_llm_post_path("google", None) == (
            f"models/{spec.default_model}:generateContent"
        )

    def test_full_url_includes_the_model(self) -> None:
        url = gateway_llm_url("google", "google/gemini-2.5-pro")
        assert url.endswith("/v1/google/models/gemini-2.5-pro:generateContent")


class TestOtherProtocolsAreUnaffected:
    @pytest.mark.parametrize(
        ("provider", "model", "expected"),
        [
            ("openai", "openai/gpt-5.6", "chat/completions"),
            ("anthropic", "anthropic/claude-sonnet-5", "messages"),
            ("groq", "groq/llama-3.3-70b-versatile", "chat/completions"),
            ("xai", "xai/grok-4", "chat/completions"),
        ],
    )
    def test_path_comes_from_the_registry_chat_path(
        self, provider: str, model: str, expected: str
    ) -> None:
        assert gateway_llm_post_path(provider, model) == expected

    def test_model_is_optional_where_it_is_not_in_the_path(self) -> None:
        assert gateway_llm_post_path("openai") == "chat/completions"


class TestPrefixStripping:
    def test_only_the_provider_segment_is_removed(self) -> None:
        """`openai/gpt-oss-120b` is a real Groq model id — the inner slash stays."""
        assert (
            gateway_llm_post_path("google", "google/models/nested-id")
            == "models/models/nested-id:generateContent"
        )

    def test_a_foreign_prefix_is_left_alone(self) -> None:
        """Not ours to strip: surface it rather than silently rewriting the caller."""
        assert (
            gateway_llm_post_path("google", "openai/gpt-5.6")
            == "models/openai/gpt-5.6:generateContent"
        )


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="not in provider registry"):
        gateway_llm_post_path("not-a-provider", "x")
