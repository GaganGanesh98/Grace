"""Governance execution record (one planned per /v1/govern call in Phase 2)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from axiom.models.base import Base


class ExecutionVerdict(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    MODIFY = "modify"
    ESCALATE = "escalate"


class ExecutionMode(StrEnum):
    SHADOW = "shadow"
    ENFORCE = "enforce"


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('approve','deny','modify','escalate')",
            name="ck_executions_verdict",
        ),
        CheckConstraint(
            "mode IN ('shadow','enforce')",
            name="ck_executions_mode",
        ),
        Index("ix_executions_project_created", "project_id", "created_at"),
        Index("ix_executions_agent", "agent_id"),
        Index("ix_executions_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_id: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    modification: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    escalation_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    correlation_id: Mapped[str] = mapped_column(Text, nullable=False)
