import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email


@pytest.mark.asyncio
async def test_patch_me(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(tokens["access_token"]),
        json={"full_name": "Updated Name", "avatar_url": None},
    )
    assert response.status_code == 200
    assert response.json()["data"]["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    response = await client.post(
        "/api/v1/users/me/password",
        headers=auth_headers(tokens["access_token"]),
        json={"current_password": "password1a", "new_password": "password2b"},
    )
    assert response.status_code == 200

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password1a"},
    )
    assert bad.status_code == 401

    good = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password2b"},
    )
    assert good.status_code == 200


@pytest.mark.asyncio
async def test_users_me_unauthorized(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/users/me", json={"full_name": "X"})
    assert response.status_code == 401
