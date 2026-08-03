"""phase 1.75 crypto schema - executions, receipts, merkle_nodes

Revision ID: b2c3d4e5f6a7
Revises: d16ea780bf45
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "d16ea780bf45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("policy_id", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("action", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=True),
        sa.Column("modification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("escalation_target", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "verdict IN ('approve','deny','modify','escalate')",
            name="ck_executions_verdict",
        ),
        sa.CheckConstraint(
            "mode IN ('shadow','enforce')",
            name="ck_executions_mode",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_executions_agent_id_agents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_executions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_executions")),
    )
    op.create_table(
        "receipts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("execution_id", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.LargeBinary(), nullable=False),
        sa.Column("ed25519_signature", sa.LargeBinary(), nullable=False),
        sa.Column("ed25519_key_id", sa.Text(), nullable=False),
        sa.Column("ml_dsa_signature", sa.LargeBinary(), nullable=False),
        sa.Column("ml_dsa_key_id", sa.Text(), nullable=False),
        sa.Column(
            "algorithm",
            sa.Text(),
            server_default=sa.text("'ed25519+ml-dsa-65'"),
            nullable=False,
        ),
        sa.Column("merkle_root", sa.LargeBinary(), nullable=True),
        sa.Column("merkle_tree_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_receipts_execution_id_executions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_receipts")),
        sa.UniqueConstraint("execution_id", name=op.f("uq_receipts_execution_id")),
    )
    op.create_table(
        "merkle_nodes",
        sa.Column("leaf_index", sa.BigInteger(), nullable=False),
        sa.Column("leaf_hash", sa.LargeBinary(), nullable=False),
        sa.Column("receipt_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.id"],
            name=op.f("fk_merkle_nodes_receipt_id_receipts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("leaf_index", name=op.f("pk_merkle_nodes")),
        sa.UniqueConstraint("leaf_hash", name=op.f("uq_merkle_nodes_leaf_hash")),
        sa.UniqueConstraint("receipt_id", name=op.f("uq_merkle_nodes_receipt_id")),
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_executions_project_created "
        "ON executions (project_id, created_at DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_executions_agent ON executions (agent_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_executions_correlation ON executions (correlation_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_receipts_execution ON receipts (execution_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_merkle_nodes_receipt ON merkle_nodes (receipt_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_merkle_nodes_receipt")
    op.execute("DROP INDEX IF EXISTS ix_receipts_execution")
    op.execute("DROP INDEX IF EXISTS ix_executions_correlation")
    op.execute("DROP INDEX IF EXISTS ix_executions_agent")
    op.execute("DROP INDEX IF EXISTS ix_executions_project_created")

    op.drop_table("merkle_nodes")
    op.drop_table("receipts")
    op.drop_table("executions")
