from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom.models.base import Base, SoftDeleteMixin, TimestampsMixin, UUIDv7Mixin

if TYPE_CHECKING:
    from axiom.models.agent import Agent
    from axiom.models.api_key import ApiKey
    from axiom.models.member import ProjectMember
    from axiom.models.policy import Policy
    from axiom.models.user import User


class Project(Base, UUIDv7Mixin, TimestampsMixin, SoftDeleteMixin):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_owner_user_id", "owner_user_id"),)

    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    settings: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    owner: Mapped[User] = relationship(
        "User",
        back_populates="owned_projects",
        foreign_keys=[owner_user_id],
        lazy="noload",
    )
    members: Mapped[list[ProjectMember]] = relationship(
        "ProjectMember",
        back_populates="project",
        lazy="noload",
    )
    agents: Mapped[list[Agent]] = relationship("Agent", back_populates="project", lazy="noload")
    policies: Mapped[list[Policy]] = relationship("Policy", back_populates="project", lazy="noload")
    api_keys: Mapped[list[ApiKey]] = relationship("ApiKey", back_populates="project", lazy="noload")
