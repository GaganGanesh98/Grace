"""Agent execution runs (Phase 6.5) — reference `agent_definitions`, not legacy `agents`."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom.models.base import Base, TimestampsMixin, UUIDv7Mixin

if TYPE_CHECKING:
    from axiom.models.agent_definition import AgentDefinition
    from axiom.models.project import Project


class AgentRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRun(Base, UUIDv7Mixin, TimestampsMixin):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_agent_runs_status",
        ),
        Index("ix_agent_runs_project_status_created", "project_id", "status", "created_at"),
        Index("ix_agent_runs_agent_definition_id", "agent_definition_id"),
        Index("ix_agent_runs_correlation_id", "correlation_id"),
        Index("ix_agent_runs_status", "status"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_definition_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(Text, nullable=False)
    input_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    final_output: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    ws_token_hash: Mapped[str | None] = mapped_column(Text)
    total_tokens: Mapped[int | None] = mapped_column(BigInteger)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    receipt_ids: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    artifacts: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    agent_definition: Mapped[AgentDefinition] = relationship("AgentDefinition", lazy="noload")
    project: Mapped[Project] = relationship("Project", lazy="noload")
