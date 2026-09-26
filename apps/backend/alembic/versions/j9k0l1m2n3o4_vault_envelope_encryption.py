"""vault_keys envelope encryption columns

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-08-08

Phase 8.2: each credential gets a per-row data key wrapped by a purpose-scoped
KEK. Three columns carry that:

* ``scheme``      — which encryption scheme wrote the row. Readers dispatch on it.
* ``kek_id``      — which KEK wrapped the DEK, so old and new keys can coexist
                    during a rotation and a key is retirable once its row count
                    reaches zero.
* ``wrapped_dek`` — the DEK, encrypted under that KEK.

All three are nullable-or-defaulted so the migration is online-safe: existing
rows keep working as ``legacy/v1`` until ``axiom keys migrate-vault`` re-seals
them. ``encrypted_key`` keeps its meaning in both schemes — the payload — so no
data moves here.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j9k0l1m2n3o4"
down_revision: Union[str, Sequence[str], None] = "i8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_SCHEME = "legacy/v1"


def upgrade() -> None:
    op.add_column(
        "vault_keys",
        sa.Column(
            "scheme",
            sa.Text(),
            server_default=sa.text(f"'{_LEGACY_SCHEME}'"),
            nullable=False,
        ),
    )
    op.add_column("vault_keys", sa.Column("kek_id", sa.Text(), nullable=True))
    op.add_column(
        "vault_keys",
        sa.Column("wrapped_dek", postgresql.BYTEA(), nullable=True),
    )
    # Cheap and small: `keys status` groups by these two on every invocation.
    op.create_index("ix_vault_keys_scheme", "vault_keys", ["scheme"], unique=False)
    op.create_index("ix_vault_keys_kek_id", "vault_keys", ["kek_id"], unique=False)


def downgrade() -> None:
    # Envelope rows cannot be read once these columns are gone: the wrapped DEK
    # is the only way back to the payload. Refuse rather than silently orphan
    # the credentials — re-seal them as legacy first if a downgrade is really
    # wanted, which is a decision an operator should make explicitly.
    bind = op.get_bind()
    remaining = bind.scalar(
        sa.text("SELECT count(*) FROM vault_keys WHERE scheme <> :legacy"),
        {"legacy": _LEGACY_SCHEME},
    )
    if remaining:
        msg = (
            f"{remaining} vault_keys row(s) use envelope encryption. Dropping "
            "wrapped_dek would make them permanently unreadable. Re-seal or "
            "delete them before downgrading."
        )
        raise RuntimeError(msg)

    op.drop_index("ix_vault_keys_kek_id", table_name="vault_keys")
    op.drop_index("ix_vault_keys_scheme", table_name="vault_keys")
    op.drop_column("vault_keys", "wrapped_dek")
    op.drop_column("vault_keys", "kek_id")
    op.drop_column("vault_keys", "scheme")
