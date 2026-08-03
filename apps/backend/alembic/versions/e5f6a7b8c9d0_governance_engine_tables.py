"""governance engine tables (intents, verdicts, receipts)

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "governance_intents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("action_type", sa.String(255), nullable=False),
        sa.Column("target", sa.String(1024), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("risk_declared", sa.String(50), nullable=False),
        sa.Column(
            "mode",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'enforce'"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_governance_intents_project_id",
        "governance_intents",
        ["project_id"],
    )
    op.create_index(
        "ix_governance_intents_created_at",
        "governance_intents",
        ["created_at"],
    )

    op.create_table(
        "governance_verdicts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance_intents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("verdict", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column(
            "rules_evaluated",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("risk_assessed", sa.String(50), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_governance_verdicts_intent_id",
        "governance_verdicts",
        ["intent_id"],
    )
    op.create_index(
        "ix_governance_verdicts_created_at",
        "governance_verdicts",
        ["created_at"],
    )

    op.create_table(
        "governance_receipts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance_intents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "verdict_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance_verdicts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("execution_data", postgresql.JSONB(), nullable=True),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("verification", sa.String(50), nullable=True),
        sa.Column(
            "mismatches",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("receipt_hash", sa.LargeBinary(), nullable=True),
        sa.Column("ed25519_sig", sa.LargeBinary(), nullable=True),
        sa.Column("ml_dsa_sig", sa.LargeBinary(), nullable=True),
        sa.Column("merkle_leaf", sa.LargeBinary(), nullable=True),
        sa.Column("merkle_root", sa.LargeBinary(), nullable=True),
        sa.Column("merkle_proof", postgresql.JSONB(), nullable=True),
        sa.Column("key_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("sealed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_governance_receipts_project_id",
        "governance_receipts",
        ["project_id"],
    )
    op.create_index(
        "ix_governance_receipts_intent_id",
        "governance_receipts",
        ["intent_id"],
    )
    op.create_index(
        "ix_governance_receipts_status",
        "governance_receipts",
        ["status"],
    )
    op.create_index(
        "ix_governance_receipts_created_at",
        "governance_receipts",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_governance_receipts_created_at", table_name="governance_receipts")
    op.drop_index("ix_governance_receipts_status", table_name="governance_receipts")
    op.drop_index("ix_governance_receipts_intent_id", table_name="governance_receipts")
    op.drop_index("ix_governance_receipts_project_id", table_name="governance_receipts")
    op.drop_table("governance_receipts")

    op.drop_index("ix_governance_verdicts_created_at", table_name="governance_verdicts")
    op.drop_index("ix_governance_verdicts_intent_id", table_name="governance_verdicts")
    op.drop_table("governance_verdicts")

    op.drop_index("ix_governance_intents_created_at", table_name="governance_intents")
    op.drop_index("ix_governance_intents_project_id", table_name="governance_intents")
    op.drop_table("governance_intents")
