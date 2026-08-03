"""Phase 2.5 governance engine ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, LargeBinary, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from axiom.models.base import Base

if TYPE_CHECKING:
    from axiom.models.project import Project
    from axiom.models.user import User


class GovernanceChain(Base):
    __tablename__ = "governance_chains"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workflow_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'active'"),
    )
    total_actions: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    authorized: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    held: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    denied: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    compliant: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    non_compliant: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    chain_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ed25519_sig: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ml_dsa_sig: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sealed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_activity: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship("Project", lazy="noload")


class GovernanceIntent(Base):
    __tablename__ = "governance_intents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(255), nullable=False)
    target: Mapped[str] = mapped_column(String(1024), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    risk_declared: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'enforce'"))
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    chain_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("governance_chains.id", ondelete="SET NULL"),
        nullable=True,
    )

    project: Mapped[Project] = relationship("Project", lazy="noload")
    chain: Mapped[GovernanceChain | None] = relationship("GovernanceChain", lazy="noload")


class GovernanceVerdict(Base):
    __tablename__ = "governance_verdicts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    intent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("governance_intents.id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    rules_evaluated: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    risk_assessed: Mapped[str] = mapped_column(String(50), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class GovernanceReceipt(Base):
    __tablename__ = "governance_receipts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    intent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("governance_intents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    verdict_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("governance_verdicts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    execution_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    verification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mismatches: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    receipt_hash: Mapped[bytes | None] = mapped_column(nullable=True)
    ed25519_sig: Mapped[bytes | None] = mapped_column(nullable=True)
    ml_dsa_sig: Mapped[bytes | None] = mapped_column(nullable=True)
    merkle_leaf: Mapped[bytes | None] = mapped_column(nullable=True)
    merkle_root: Mapped[bytes | None] = mapped_column(nullable=True)
    merkle_proof: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")
    sealed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=func.now(),
    )
    approval_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approval_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    project: Mapped[Project] = relationship("Project", lazy="noload")
    approved_by_user: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[approved_by_user_id],
        lazy="noload",
    )
