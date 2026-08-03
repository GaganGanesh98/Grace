"""Phase 2.3: Google OAuth HTTP flow and misconfiguration responses."""

from typing import Any

import pytest
from httpx import AsyncClient

from axiom.config import get_settings


@pytest.mark.asyncio
async def test_google_authorize_503_when_oauth_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    get_settings.cache_clear()
    try:
        response = await client.get("/api/v1/auth/google/authorize")
        assert response.status_code == 503
        body: dict[str, Any] = response.json()
        message = body["error"]["message"]
        assert "GOOGLE_CLIENT_ID" in message
        assert "GOOGLE_CLIENT_SECRET" in message
        assert "docs/auth-setup.md" in message
    finally:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-google-secret")
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_google_callback_state_mismatch_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/google/callback",
        json={"code": "x", "state": "invalid-state"},
    )
    assert response.status_code == 400
