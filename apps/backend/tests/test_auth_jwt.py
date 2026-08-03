from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from axiom.config import get_settings
from tests.conftest import auth_headers, signup_user, unique_email


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    response = await client.get(
        "/api/v1/auth/me",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == email


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_tampered_token(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    tampered = tokens["access_token"][:-4] + "xxxx"
    response = await client.get("/api/v1/auth/me", headers=auth_headers(tampered))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_flow(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    new_tokens = response.json()["data"]
    assert new_tokens["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_expired_access_token_rejected(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    user_id = me.json()["data"]["id"]
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=2)
    expired = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "iat": past,
            "exp": past,
            "jti": "expired-jti",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    response = await client.get("/api/v1/auth/me", headers=auth_headers(expired))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    logout = await client.post(
        "/api/v1/auth/logout",
        headers=auth_headers(tokens["access_token"]),
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == 200

    refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 401
