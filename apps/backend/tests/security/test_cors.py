import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.security
async def test_cors_does_not_reflect_evil_origin(client: AsyncClient) -> None:
    response = await client.get(
        "/healthz",
        headers={"Origin": "https://evil.com"},
    )
    assert response.status_code == 200
    allow = response.headers.get("access-control-allow-origin")
    assert allow != "https://evil.com"
