from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from pytest_httpx import HTTPXMock

from axiom.services import google_oauth
from tests.conftest import unique_email
from tests.fixtures.google_jwks import make_google_id_token


@pytest.mark.asyncio
async def test_google_authorize_returns_url_and_state(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/google/authorize")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "accounts.google.com" in data["url"]
    assert data["state"]


@pytest.mark.asyncio
async def test_google_callback_success(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
) -> None:
    async def fake_exchange(*, code: str, state: str | None) -> dict[str, object]:
        _ = code
        _ = state
        return {
            "sub": f"google-sub-{uuid4()}",
            "email": unique_email(),
            "name": "G User",
        }

    monkeypatch.setattr(google_oauth, "exchange_code", fake_exchange)

    auth = await client.get("/api/v1/auth/google/authorize")
    state = auth.json()["data"]["state"]

    response = await client.post(
        "/api/v1/auth/google/callback",
        json={"code": "fake-code", "state": state},
    )
    assert response.status_code == 200, response.text
    tokens = response.json()["data"]
    assert "access_token" in tokens


@pytest.mark.asyncio
async def test_google_callback_invalid_state(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/google/callback",
        json={"code": "x", "state": "invalid-state"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_google_callback_no_state(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/google/callback",
        json={"code": "x"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_google_callback_valid_id_token(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
    client: AsyncClient,
) -> None:
    priv, _ = google_rsa_keypair
    id_token = make_google_id_token(priv, sub=f"route-{uuid4().hex}", email=unique_email())
    auth = await client.get("/api/v1/auth/google/authorize")
    state = auth.json()["data"]["state"]
    httpx_mock.add_response(
        method="POST",
        url="https://oauth2.googleapis.com/token",
        json={"id_token": id_token},
    )
    response = await client.post(
        "/api/v1/auth/google/callback",
        json={"code": "auth-code", "state": state},
    )
    assert response.status_code == 200, response.text
    assert "access_token" in response.json()["data"]
