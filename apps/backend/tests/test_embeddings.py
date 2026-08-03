"""Unit tests for the swappable embedding service (no DB, no real model)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from pytest_httpx import HTTPXMock

from axiom.services.embeddings import service as emb


class _FakeProvider:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._mapping[text] for text in texts]


@pytest.fixture(autouse=True)
def _reset_provider() -> Iterator[None]:
    emb.reset_provider()
    yield
    emb.reset_provider()


async def test_embed_texts_and_query_use_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    vector = [0.1] * emb.EMBEDDING_DIM
    provider = _FakeProvider({"hello": vector})
    monkeypatch.setattr(emb, "_get_provider", lambda: provider)
    assert await emb.embed_texts(["hello"]) == [vector]
    assert await emb.embed_query("hello") == vector


async def test_embed_texts_empty_returns_empty() -> None:
    assert await emb.embed_texts([]) == []


async def test_wrong_dimension_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(emb, "_get_provider", lambda: _FakeProvider({"x": [0.0, 0.1]}))
    with pytest.raises(emb.EmbeddingError):
        await emb.embed_texts(["x"])


async def test_provider_exception_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        def embed(self, texts: list[str]) -> list[list[float]]:  # noqa: ARG002
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(emb, "_get_provider", _Boom)
    with pytest.raises(emb.EmbeddingError, match="model unavailable"):
        await emb.embed_texts(["x"])


def test_openai_provider_calls_api_with_pinned_dimensions(httpx_mock: HTTPXMock) -> None:
    vector = [0.2] * emb.EMBEDDING_DIM
    httpx_mock.add_response(
        url="https://api.openai.com/v1/embeddings",
        json={"data": [{"index": 0, "embedding": vector}]},
    )
    provider = emb.OpenAIEmbedProvider(
        "text-embedding-3-small", "sk-test", "https://api.openai.com/v1"
    )
    assert provider.embed(["hello"]) == [vector]

    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["Authorization"] == "Bearer sk-test"
    body = json.loads(request.content)
    assert body["model"] == "text-embedding-3-small"
    assert body["input"] == ["hello"]
    # dimensions pinned so OpenAI matches the pgvector column (no re-migration).
    assert body["dimensions"] == emb.EMBEDDING_DIM


def test_openai_provider_orders_by_index(httpx_mock: HTTPXMock) -> None:
    a = [0.1] * emb.EMBEDDING_DIM
    b = [0.9] * emb.EMBEDDING_DIM
    httpx_mock.add_response(
        url="https://api.openai.com/v1/embeddings",
        # Deliberately out of order — provider must sort by index.
        json={"data": [{"index": 1, "embedding": b}, {"index": 0, "embedding": a}]},
    )
    provider = emb.OpenAIEmbedProvider(
        "text-embedding-3-small", "sk-test", "https://api.openai.com/v1"
    )
    assert provider.embed(["first", "second"]) == [a, b]


def test_openai_provider_requires_key_via_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from axiom.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AXIOM_EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("AXIOM_EMBEDDING_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    emb.reset_provider()
    with pytest.raises(emb.EmbeddingError, match="no AXIOM_EMBEDDING_OPENAI_API_KEY"):
        emb._get_provider()
    get_settings.cache_clear()
