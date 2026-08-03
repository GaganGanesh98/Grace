"""Phase 7.2 — agent_runs.artifacts JSONB for tool outputs.

Revision ID: g1h2i3j4k5l6
Revises: f9c1d2e3a4b7
Create Date: 2026-04-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, Sequence[str], None] = "f9c1d2e3a4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "artifacts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "artifacts")
