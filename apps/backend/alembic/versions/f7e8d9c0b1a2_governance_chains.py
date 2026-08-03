"""governance chains (workflow grouping + chain_id on intents)

Revision ID: f7e8d9c0b1a2
Revises: e5f6a7b8c9d0
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7e8d9c0b1a2"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "governance_chains",
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
        sa.Column("workflow_name", sa.String(255), nullable=True),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "total_actions",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "authorized",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "held",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "denied",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "compliant",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "non_compliant",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("chain_hash", sa.LargeBinary(), nullable=True),
        sa.Column("ed25519_sig", sa.LargeBinary(), nullable=True),
        sa.Column("ml_dsa_sig", sa.LargeBinary(), nullable=True),
        sa.Column("key_id", sa.String(255), nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sealed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "last_activity",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        "ix_governance_chains_project_id",
        "governance_chains",
        ["project_id"],
    )
    op.create_index(
        "ix_governance_chains_agent_id",
        "governance_chains",
        ["agent_id"],
    )
    op.create_index(
        "ix_governance_chains_status",
        "governance_chains",
        ["status"],
    )
    op.create_index(
        "ix_governance_chains_last_activity",
        "governance_chains",
        ["last_activity"],
    )

    op.add_column(
        "governance_intents",
        sa.Column(
            "chain_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance_chains.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_governance_intents_chain_id",
        "governance_intents",
        ["chain_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_governance_intents_chain_id", table_name="governance_intents")
    op.drop_column("governance_intents", "chain_id")

    op.drop_index("ix_governance_chains_last_activity", table_name="governance_chains")
    op.drop_index("ix_governance_chains_status", table_name="governance_chains")
    op.drop_index("ix_governance_chains_agent_id", table_name="governance_chains")
    op.drop_index("ix_governance_chains_project_id", table_name="governance_chains")
    op.drop_table("governance_chains")
