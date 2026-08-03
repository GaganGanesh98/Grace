"""add approval fields to governance_receipts

Revision ID: a1b2c3d4e5f7
Revises: f7e8d9c0b1a2
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f7e8d9c0b1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "governance_receipts",
        sa.Column("approval_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "governance_receipts",
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "governance_receipts",
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "governance_receipts",
        sa.Column("approval_reason", sa.String(500), nullable=True),
    )
    op.add_column(
        "governance_receipts",
        sa.Column("approval_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_governance_receipts_approval_pending",
        "governance_receipts",
        ["project_id", "approval_status"],
        postgresql_where=sa.text("approval_status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_governance_receipts_approval_pending",
        table_name="governance_receipts",
    )
    op.drop_column("governance_receipts", "approval_expires_at")
    op.drop_column("governance_receipts", "approval_reason")
    op.drop_column("governance_receipts", "approved_at")
    op.drop_column("governance_receipts", "approved_by_user_id")
    op.drop_column("governance_receipts", "approval_status")
