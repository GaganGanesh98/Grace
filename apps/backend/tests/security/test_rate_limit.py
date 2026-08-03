import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_rate_limit_per_ip(client: AsyncClient) -> None:
    last = None
    for i in range(6):
        last = await client.post(
            "/api/v1/auth/login",
            json={"email": f"rate-{i}@example.com", "password": "wrong1a"},
        )
    assert last is not None
    assert last.status_code == 429
