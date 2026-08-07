"""Swappable text-embedding provider for semantic policy matching.

Default provider is **fastembed** (BAAI/bge-small-en-v1.5): local, free, offline,
no API key. Set ``AXIOM_EMBEDDING_PROVIDER=openai`` to use OpenAI
``text-embedding-3-small`` via httpx instead. Both emit ``EMBEDDING_DIM`` (384)
vectors — the OpenAI path passes ``dimensions=384`` — so the pgvector column and
migration never change when you switch providers.

Heavy imports (fastembed / onnxruntime) are deferred to first use so importing
this module (e.g. from the Policy model, for ``EMBEDDING_DIM``) stays cheap.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

import httpx

from axiom.config import get_settings
from axiom.core.embedding_dim import EMBEDDING_DIM as _EMBEDDING_DIM

# BAAI/bge-small-en-v1.5 native dim; OpenAI text-embedding-3-small supports
# dimensions=384. The constant itself lives in axiom.core so that
# axiom.models.policy can declare its Vector column without importing a
# service (see .importlinter contracts 1 and 2); re-exported here so existing
# `from axiom.services.embeddings import EMBEDDING_DIM` callers keep working.
EMBEDDING_DIM = _EMBEDDING_DIM


class EmbeddingError(RuntimeError):
    """The configured embedding provider failed to produce vectors."""


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedProvider:
    """Local ONNX embeddings via fastembed. Model is loaded once, lazily."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: object | None = None

    def _ensure_model(self) -> object:
        if self._model is None:
            from fastembed import TextEmbedding  # lazy: pulls onnxruntime

            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vectors = model.embed(texts)  # type: ignore[attr-defined]
        return [[float(x) for x in vector] for vector in vectors]


class OpenAIEmbedProvider:
    """OpenAI embeddings via httpx (no openai SDK dependency)."""

    def __init__(self, model_name: str, api_key: str, base_url: str) -> None:
        self._model = model_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "input": texts, "dimensions": EMBEDDING_DIM},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in rows]


def _build_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = (settings.embedding_provider or "fastembed").lower()
    if provider == "openai":
        secret = settings.embedding_openai_api_key
        key = secret.get_secret_value() if secret else ""
        if not key:
            raise EmbeddingError(
                "AXIOM_EMBEDDING_PROVIDER=openai but no AXIOM_EMBEDDING_OPENAI_API_KEY set"
            )
        return OpenAIEmbedProvider(
            settings.embedding_model, key, settings.embedding_openai_base_url
        )
    if provider != "fastembed":
        raise EmbeddingError(f"unknown AXIOM_EMBEDDING_PROVIDER: {provider!r}")
    return FastEmbedProvider(settings.embedding_model)


_provider_singleton: EmbeddingProvider | None = None


def _get_provider() -> EmbeddingProvider:
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = _build_provider()
    return _provider_singleton


def reset_provider() -> None:
    """Drop the cached provider (used by tests that swap env/config)."""
    global _provider_singleton
    _provider_singleton = None


def _embed_sync(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        vectors = _get_provider().embed(texts)
    except EmbeddingError:
        raise
    except Exception as exc:  # provider/model/HTTP failure
        raise EmbeddingError(str(exc)) from exc
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise EmbeddingError(f"provider returned dim {len(vector)}, expected {EMBEDDING_DIM}")
    return vectors


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts off the event loop (providers are CPU/IO-bound)."""
    return await asyncio.to_thread(_embed_sync, texts)


async def embed_query(text: str) -> list[float]:
    """Embed a single query string; returns one ``EMBEDDING_DIM`` vector."""
    vectors = await embed_texts([text])
    return vectors[0]
