from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.conftest import unique_email


@pytest.mark.asyncio
@pytest.mark.security
async def test_google_callback_requires_state(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/google/callback",
        json={"code": "dummy-code"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.security
async def test_google_id_token_decode_checks_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    from axiom.services import google_oauth as go

    calls: dict[str, object] = {}

    def fake_decode(token: str, key: object, **kwargs: object) -> dict[str, str]:
        calls["audience"] = kwargs.get("audience")
        return {"sub": "sub", "email": unique_email(), "email_verified": True}

    jwks = [{"kid": "k1", "kty": "RSA"}]
    monkeypatch.setattr(go, "_fetch_google_jwks", AsyncMock(return_value=jwks))
    monkeypatch.setattr(go.jwt, "get_unverified_header", lambda _t: {"kid": "k1", "alg": "RS256"})
    monkeypatch.setattr(go.jwk, "construct", lambda _d: object())
    monkeypatch.setattr(go.jwt, "decode", fake_decode)

    from axiom.config import get_settings

    settings = get_settings()
    await go.verify_google_id_token("dummy.token.value")
    assert calls["audience"] == settings.google_client_id
