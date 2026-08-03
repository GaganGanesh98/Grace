"""Merkle audit chain leaf row (one per receipt, ordered by leaf_index within a project).

Phase 2: trees are per-project. Composite primary key is (project_id, leaf_index);
leaf hashes are unique within a project (not globally).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from axiom.models.base import Base


class MerkleNode(Base):
    __tablename__ = "merkle_nodes"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "leaf_hash",
            name="uq_merkle_nodes_project_leaf_hash",
        ),
        Index(
            "ix_merkle_nodes_project_created",
            "project_id",
            "created_at",
        ),
        Index("ix_merkle_nodes_receipt", "receipt_id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    leaf_index: Mapped[int] = mapped_column(
        BigInteger(),
        primary_key=True,
        autoincrement=False,
    )
    leaf_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    receipt_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("receipts.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
