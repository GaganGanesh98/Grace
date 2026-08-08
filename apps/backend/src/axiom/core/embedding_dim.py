"""Embedding vector dimensionality — a leaf constant.

This lives in ``axiom.core`` rather than ``axiom.services.embeddings`` because
``axiom.models.policy`` needs it to declare its ``Vector(...)`` column, and
models are forbidden from importing services (``.importlinter`` contracts 1
and 2). A single int does not justify breaking the layering.

Kept in sync with the Alembic migration's ``EMBEDDING_DIM`` and with the
provider configuration in ``axiom.services.embeddings.service`` (fastembed
``BAAI/bge-small-en-v1.5`` and OpenAI ``text-embedding-3-small`` with
``dimensions=384`` both emit 384). Changing this value requires a migration
that rebuilds the ``policies.embedding`` column and its HNSW index.
"""

from __future__ import annotations

EMBEDDING_DIM = 384

__all__ = ["EMBEDDING_DIM"]
