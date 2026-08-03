"""Encrypted credentials per user (vault): LLM providers and external tools."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom.models.base import Base, TimestampsMixin, UUIDv7Mixin

if TYPE_CHECKING:
    from axiom.models.user import User


class VaultKey(Base, UUIDv7Mixin, TimestampsMixin):
    __tablename__ = "vault_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "service", "name", name="uq_vault_keys_user_service_name"),
        Index("ix_vault_keys_user", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'llm'"))
    encrypted_key: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_suffix: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    user: Mapped[User] = relationship("User", lazy="noload", foreign_keys=[user_id])
