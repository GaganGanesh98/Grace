from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom.models.base import Base, SoftDeleteMixin, TimestampsMixin, UUIDv7Mixin
from axiom.services.embeddings import EMBEDDING_DIM

if TYPE_CHECKING:
    from axiom.models.project import Project


class Policy(Base, UUIDv7Mixin, TimestampsMixin, SoftDeleteMixin):
    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", "version", name="uq_policies_slug_version"),
        Index(
            "ix_policies_project_id_is_active_active",
            "project_id",
            "is_active",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    pack: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'custom'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    rules: Mapped[list[object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Semantic embedding of the policy text (name + description + rule
    # descriptions). Nullable: populated best-effort on write, never blocking.
    # HNSW cosine index (ix_policies_embedding_hnsw) is created in the migration.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="policies", lazy="noload")
