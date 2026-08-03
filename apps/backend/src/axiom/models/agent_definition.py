"""Runnable agent configuration (Phase 6.5) — attached to legacy `agents` rows."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom.models.base import Base, TimestampsMixin, UUIDv7Mixin

if TYPE_CHECKING:
    from axiom.models.agent import Agent
    from axiom.models.project import Project
    from axiom.models.user import User
    from axiom.models.vault import VaultKey


class AgentDefinition(Base, UUIDv7Mixin, TimestampsMixin):
    __tablename__ = "agent_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_agent_definitions_project_name"),
        Index("ix_agent_definitions_agent_id", "agent_id"),
        Index("ix_agent_definitions_project_id", "project_id"),
        Index("ix_agent_definitions_created_by", "created_by"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(1024), nullable=False)
    vault_key_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("vault_keys.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tools_config: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    max_tokens_per_run: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("100000")
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    project: Mapped[Project] = relationship("Project", lazy="noload")
    agent: Mapped[Agent] = relationship("Agent", lazy="noload")
    vault_key: Mapped[VaultKey] = relationship("VaultKey", lazy="noload")
    creator: Mapped[User] = relationship("User", lazy="noload", foreign_keys=[created_by])
