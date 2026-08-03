import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import unique_email


@pytest.mark.asyncio
@pytest.mark.security
async def test_signup_rate_limited_per_ip(client: AsyncClient) -> None:
    last = None
    for _ in range(11):
        email = unique_email()
        last = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "password1a",
                "full_name": str(uuid.uuid4()),
            },
        )
    assert last is not None
    assert last.status_code == 429
