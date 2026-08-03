"""Overrides for crypto unit tests (no Redis / DB)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest


@pytest.fixture(autouse=True)
async def _reset_redis_between_tests() -> AsyncIterator[None]:
    """Pure crypto tests do not need Redis; override the suite-wide autouse fixture."""
    yield
