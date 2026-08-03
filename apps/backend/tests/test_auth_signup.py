import pytest
from httpx import AsyncClient

from tests.conftest import signup_user, unique_email


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient) -> None:
    email = unique_email()
    data = await signup_user(client, email, "password1a")
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "password1b", "full_name": "Other"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_signup_duplicate_email_case_insensitive(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email.upper(), "password": "password1b", "full_name": "Other"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_signup_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": unique_email(), "password": "short", "full_name": "A"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_weak_password_no_digit(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": unique_email(), "password": "onlyletters", "full_name": "A"},
    )
    assert response.status_code == 422
