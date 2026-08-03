"""Phase 2.3: signup API flow (E2E-style via ASGI transport)."""

import pytest
from httpx import AsyncClient

from tests.conftest import signup_user, unique_email


@pytest.mark.asyncio
async def test_signup_flow_returns_tokens(client: AsyncClient) -> None:
    email = unique_email()
    data = await signup_user(client, email, "password1a")
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_signup_invalid_email_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "password": "password1a", "full_name": "X"},
    )
    assert response.status_code == 422
