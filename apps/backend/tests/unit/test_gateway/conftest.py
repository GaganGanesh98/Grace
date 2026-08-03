"""Gateway ASGI client and shared fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from axiom.config import get_settings
from axiom.gateway.app import app


@pytest.fixture
async def gateway_client() -> AsyncIterator[AsyncClient]:
    get_settings.cache_clear()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://gateway.test") as ac:
        yield ac
