"""Phase 6.5 — agent_definitions table

Revision ID: f8c1d2e3a4b5
Revises: c4d5e6f7a8b9
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8c1d2e3a4b5"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=512), nullable=False),
        sa.Column("vault_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tools_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("max_iterations", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("max_tokens_per_run", sa.Integer(), server_default=sa.text("100000"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vault_key_id"], ["vault_keys.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_agent_definitions_project_name"),
    )
    op.create_index("ix_agent_definitions_agent_id", "agent_definitions", ["agent_id"], unique=False)
    op.create_index("ix_agent_definitions_project_id", "agent_definitions", ["project_id"], unique=False)
    op.create_index("ix_agent_definitions_created_by", "agent_definitions", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_definitions_created_by", table_name="agent_definitions")
    op.drop_index("ix_agent_definitions_project_id", table_name="agent_definitions")
    op.drop_index("ix_agent_definitions_agent_id", table_name="agent_definitions")
    op.drop_table("agent_definitions")
