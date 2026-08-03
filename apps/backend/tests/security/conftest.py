from __future__ import annotations

import importlib
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def disable_auth_login_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable slowapi for lockout tests (same client IP would otherwise hit login RL first)."""
    from axiom.middleware import rate_limit as rate_limit_mod

    monkeypatch.setattr(rate_limit_mod.limiter, "enabled", False)


@pytest.fixture
async def production_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """Fresh app with ENVIRONMENT=production (docs/OpenAPI disabled)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    import axiom.config as cfg

    cfg.get_settings.cache_clear()
    import axiom.main as main_mod

    importlib.reload(main_mod)
    transport = ASGITransport(app=main_mod.app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    monkeypatch.setenv("ENVIRONMENT", "development")
    cfg.get_settings.cache_clear()
    importlib.reload(main_mod)
