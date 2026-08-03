"""Time-ordered UUIDs aligned with PostgreSQL ``uuidv7()`` usage."""

from __future__ import annotations

from uuid import UUID

from uuid6 import uuid7


def new_uuidv7() -> UUID:
    """Return a new UUID version 7 (time-sortable)."""
    return uuid7()


def new_uuidv7_str() -> str:
    """String form for ``Text`` / ``VARCHAR`` correlation identifiers."""
    return str(uuid7())
