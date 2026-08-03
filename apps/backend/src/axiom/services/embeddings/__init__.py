"""Text-embedding service (semantic policy matching).

See :mod:`axiom.services.embeddings.service`. Importing this package is cheap —
the embedding backend (fastembed / onnxruntime) is loaded lazily on first use.
"""

from axiom.services.embeddings.service import (
    EMBEDDING_DIM,
    EmbeddingError,
    embed_query,
    embed_texts,
    reset_provider,
)

__all__ = [
    "EMBEDDING_DIM",
    "EmbeddingError",
    "embed_query",
    "embed_texts",
    "reset_provider",
]
