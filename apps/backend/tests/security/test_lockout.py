import pytest
from httpx import AsyncClient

from tests.conftest import signup_user, unique_email


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.usefixtures("disable_auth_login_rate_limit")
async def test_account_lockout_after_failed_attempts(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    for _ in range(5):
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong1a"},
        )
        assert r.status_code == 401
    locked = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password1a"},
    )
    assert locked.status_code == 429
    body = locked.json()
    assert body["error"]["code"] == "account_locked"


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.usefixtures("disable_auth_login_rate_limit")
async def test_lockout_email_normalized_across_case(client: AsyncClient) -> None:
    normalized = unique_email()
    local, domain = normalized.split("@", 1)
    variant_a = f"{local.upper()}@{domain}"
    variant_b = normalized
    await signup_user(client, normalized, "password1a")
    for variant in (variant_a, variant_b):
        for _ in range(2):
            await client.post(
                "/api/v1/auth/login",
                json={"email": variant, "password": "wrong1a"},
            )
    await client.post(
        "/api/v1/auth/login",
        json={"email": variant_b, "password": "wrong1a"},
    )
    locked = await client.post(
        "/api/v1/auth/login",
        json={"email": variant_a, "password": "password1a"},
    )
    assert locked.status_code == 429


@pytest.mark.asyncio
@pytest.mark.security
async def test_successful_login_clears_failed_counter(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    for _ in range(4):
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong1a"},
        )
    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password1a"},
    )
    assert ok.status_code == 200
