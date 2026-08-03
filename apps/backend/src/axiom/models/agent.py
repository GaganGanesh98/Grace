from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom.models.base import Base, SoftDeleteMixin, TimestampsMixin, UUIDv7Mixin

if TYPE_CHECKING:
    from axiom.models.project import Project


class AgentMode(StrEnum):
    ENFORCE = "enforce"
    SHADOW = "shadow"
    AUDIT = "audit"


class Agent(Base, UUIDv7Mixin, TimestampsMixin, SoftDeleteMixin):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_agents_project_slug"),
        CheckConstraint(
            "default_mode IN ('enforce','shadow','audit')",
            name="ck_agents_default_mode",
        ),
        Index(
            "ix_agents_project_id_is_active_active",
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
    agent_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'custom'"))
    default_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'shadow'")
    )
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    project: Mapped[Project] = relationship("Project", back_populates="agents", lazy="noload")
