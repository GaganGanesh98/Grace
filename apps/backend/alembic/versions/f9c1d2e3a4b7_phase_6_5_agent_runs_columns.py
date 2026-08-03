"""Phase 6.5 — agent_definitions / agent_runs schema amendments (Batch A corrections 1–6)

Revision ID: f9c1d2e3a4b7
Revises: f9c1d2e3a4b6
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9c1d2e3a4b7"
down_revision: Union[str, Sequence[str], None] = "f9c1d2e3a4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "agent_definitions",
        "model",
        existing_type=sa.String(length=512),
        type_=sa.String(length=1024),
        existing_nullable=False,
    )

    op.add_column(
        "agent_runs",
        sa.Column("total_tokens", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column("total_cost_usd", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column("last_heartbeat_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "receipt_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.execute('ALTER TABLE agent_runs RENAME COLUMN output_payload TO final_output')

    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")

    op.execute("ALTER TABLE agent_runs RENAME COLUMN final_output TO output_payload")

    op.drop_column("agent_runs", "receipt_ids")
    op.drop_column("agent_runs", "last_heartbeat_at")
    op.drop_column("agent_runs", "total_cost_usd")
    op.drop_column("agent_runs", "total_tokens")

    op.alter_column(
        "agent_definitions",
        "model",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=512),
        existing_nullable=False,
    )
