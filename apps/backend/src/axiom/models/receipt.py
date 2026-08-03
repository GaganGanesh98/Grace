"""Cryptographic receipt for a governance execution."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from axiom.models.base import Base


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (Index("ix_receipts_execution", "execution_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("executions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    payload_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ed25519_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ed25519_key_id: Mapped[str] = mapped_column(Text, nullable=False)
    ml_dsa_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ml_dsa_key_id: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ed25519+ml-dsa-65'")
    )
    merkle_root: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    merkle_tree_size: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    evidence_nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    evidence_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    evidence_key_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
