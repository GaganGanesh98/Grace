"""add policy embedding column + pgvector extension

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-08-03

Semantic policy matching: enables the pgvector extension and adds a nullable
384-dim embedding column to ``policies`` with an HNSW cosine index. 384 matches
BAAI/bge-small-en-v1.5 (the free local default) and OpenAI text-embedding-3-small
with dimensions=384, so the provider is swappable without a re-migration.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Kept in sync with axiom.services.embeddings.EMBEDDING_DIM (migrations stay
# self-contained, so the literal is intentionally duplicated here).
EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "policies",
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )
    # HNSW index for cosine distance (<=>). Only non-null rows are indexed;
    # policies whose embedding failed to compute simply won't match.
    op.execute(
        "CREATE INDEX ix_policies_embedding_hnsw "
        "ON policies USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_policies_embedding_hnsw")
    op.drop_column("policies", "embedding")
    # The `vector` extension is left installed — other objects may rely on it.
