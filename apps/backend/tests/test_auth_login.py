import pytest
from httpx import AsyncClient
from sqlalchemy import select

from axiom.db import session_scope
from axiom.models.user import User
from tests.conftest import login_user, signup_user, unique_email


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    data = await login_user(client, email, "password1a")
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrongpass1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "password1a"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        user.is_active = False
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password1a"},
    )
    assert response.status_code == 403
