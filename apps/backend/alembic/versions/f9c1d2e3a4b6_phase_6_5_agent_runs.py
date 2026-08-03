"""Phase 6.5 — agent_runs table

Revision ID: f9c1d2e3a4b6
Revises: f8c1d2e3a4b5
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9c1d2e3a4b6"
down_revision: Union[str, Sequence[str], None] = "f8c1d2e3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ws_token_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_agent_runs_status",
        ),
        sa.ForeignKeyConstraint(["agent_definition_id"], ["agent_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_runs_project_status_created",
        "agent_runs",
        ["project_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_runs_agent_definition_id",
        "agent_runs",
        ["agent_definition_id"],
        unique=False,
    )
    op.create_index("ix_agent_runs_correlation_id", "agent_runs", ["correlation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_runs_correlation_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_definition_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_project_status_created", table_name="agent_runs")
    op.drop_table("agent_runs")
