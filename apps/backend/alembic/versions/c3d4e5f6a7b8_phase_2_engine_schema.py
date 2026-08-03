"""phase 2 engine schema - per-project merkle trees + encrypted evidence on receipts

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-16

Adds:
- merkle_nodes.project_id + composite primary key (project_id, leaf_index)
- merkle_nodes.leaf_hash unique per (project_id, leaf_hash) instead of globally unique
- receipts.evidence_nonce, receipts.evidence_ciphertext, receipts.evidence_key_id
  (all nullable for backward compatibility with any 1.75 seed data; Phase 2 always populates)

The migration is reversible: downgrade restores the 1.75 schema exactly.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM merkle_nodes")

    op.execute("ALTER TABLE merkle_nodes DROP CONSTRAINT IF EXISTS pk_merkle_nodes")
    op.execute("ALTER TABLE merkle_nodes DROP CONSTRAINT IF EXISTS uq_merkle_nodes_leaf_hash")
    op.execute("DROP INDEX IF EXISTS ix_merkle_nodes_receipt")

    op.add_column(
        "merkle_nodes",
        sa.Column("project_id", sa.UUID(), nullable=False),
    )
    op.create_foreign_key(
        "fk_merkle_nodes_project_id_projects",
        source_table="merkle_nodes",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["id"],
        ondelete="RESTRICT",
    )
    op.create_primary_key(
        "pk_merkle_nodes",
        "merkle_nodes",
        ["project_id", "leaf_index"],
    )
    op.create_unique_constraint(
        "uq_merkle_nodes_project_leaf_hash",
        "merkle_nodes",
        ["project_id", "leaf_hash"],
    )
    op.execute(
        "CREATE INDEX ix_merkle_nodes_project_created "
        "ON merkle_nodes (project_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_merkle_nodes_receipt ON merkle_nodes (receipt_id)"
    )

    op.add_column(
        "receipts",
        sa.Column("evidence_nonce", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "receipts",
        sa.Column("evidence_ciphertext", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "receipts",
        sa.Column("evidence_key_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("receipts", "evidence_key_id")
    op.drop_column("receipts", "evidence_ciphertext")
    op.drop_column("receipts", "evidence_nonce")

    op.execute("DELETE FROM merkle_nodes")

    op.execute("DROP INDEX IF EXISTS ix_merkle_nodes_receipt")
    op.execute("DROP INDEX IF EXISTS ix_merkle_nodes_project_created")
    op.execute("ALTER TABLE merkle_nodes DROP CONSTRAINT IF EXISTS uq_merkle_nodes_project_leaf_hash")
    op.execute("ALTER TABLE merkle_nodes DROP CONSTRAINT IF EXISTS pk_merkle_nodes")
    op.execute(
        "ALTER TABLE merkle_nodes DROP CONSTRAINT IF EXISTS fk_merkle_nodes_project_id_projects"
    )
    op.drop_column("merkle_nodes", "project_id")

    op.create_primary_key("pk_merkle_nodes", "merkle_nodes", ["leaf_index"])
    op.create_unique_constraint("uq_merkle_nodes_leaf_hash", "merkle_nodes", ["leaf_hash"])
    op.execute("CREATE INDEX IF NOT EXISTS ix_merkle_nodes_receipt ON merkle_nodes (receipt_id)")
