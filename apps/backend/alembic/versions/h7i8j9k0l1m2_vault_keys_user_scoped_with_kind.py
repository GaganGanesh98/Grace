"""vault_keys user scoped with kind column

Revision ID: h7i8j9k0l1m2
Revises: g1h2i3j4k5l6
Create Date: 2026-05-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision: str = "h7i8j9k0l1m2"
down_revision: Union[str, Sequence[str], None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_if_column(bind: sa.Connection, table: str, column: str) -> None:
    insp = inspect(bind)
    for fk in insp.get_foreign_keys(table):
        if column in fk["constrained_columns"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
            return


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "vault_keys",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_vault_keys_user_id_users",
        "vault_keys",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        sa.text(
            """
            UPDATE vault_keys
            SET user_id = (
              SELECT user_id FROM project_members
              WHERE project_id = vault_keys.project_id
              AND role = 'OWNER'
              LIMIT 1
            )
            """
        )
    )

    op.alter_column("vault_keys", "user_id", nullable=False)

    op.add_column(
        "vault_keys",
        sa.Column(
            "kind",
            sa.Text(),
            server_default=sa.text("'llm'"),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "ALTER TABLE vault_keys ADD CONSTRAINT ck_vault_keys_kind "
            "CHECK (kind IN ('llm', 'tool', 'custom'))"
        )
    )

    op.drop_constraint("uq_vault_keys_project_provider_name", "vault_keys", type_="unique")
    op.drop_index("ix_vault_keys_project_id_provider_active", table_name="vault_keys")

    _drop_fk_if_column(bind, "vault_keys", "project_id")
    op.drop_column("vault_keys", "project_id")

    op.alter_column("vault_keys", "provider", new_column_name="service")

    op.create_unique_constraint(
        "uq_vault_keys_user_service_name",
        "vault_keys",
        ["user_id", "service", "name"],
    )
    op.create_index("ix_vault_keys_user", "vault_keys", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_vault_keys_user", table_name="vault_keys")
    op.drop_constraint("uq_vault_keys_user_service_name", "vault_keys", type_="unique")

    op.alter_column("vault_keys", "service", new_column_name="provider")

    op.add_column(
        "vault_keys",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_vault_keys_project_id_projects",
        "vault_keys",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        sa.text(
            """
            UPDATE vault_keys vk
            SET project_id = (
              SELECT pm.project_id
              FROM project_members pm
              WHERE pm.user_id = vk.user_id
              AND pm.role = 'OWNER'
              LIMIT 1
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE vault_keys
            SET project_id = (SELECT id FROM projects ORDER BY created_at LIMIT 1)
            WHERE project_id IS NULL
            """
        )
    )
    op.alter_column("vault_keys", "project_id", nullable=False)

    op.create_unique_constraint(
        "uq_vault_keys_project_provider_name",
        "vault_keys",
        ["project_id", "provider", "name"],
    )
    op.create_index(
        "ix_vault_keys_project_id_provider_active",
        "vault_keys",
        ["project_id", "provider"],
        unique=False,
    )

    op.execute(sa.text("ALTER TABLE vault_keys DROP CONSTRAINT IF EXISTS ck_vault_keys_kind"))
    op.drop_column("vault_keys", "kind")

    _drop_fk_if_column(bind, "vault_keys", "user_id")
    op.drop_column("vault_keys", "user_id")
