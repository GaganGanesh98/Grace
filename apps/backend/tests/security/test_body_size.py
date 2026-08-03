import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.security
async def test_oversized_body_returns_413(client: AsyncClient) -> None:
    big = 2 * 1024 * 1024
    response = await client.post(
        "/api/v1/auth/login",
        headers={"content-length": str(big)},
        content=b"x",
    )
    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "payload_too_large"
