import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}


@pytest.mark.asyncio
async def test_readyz_structure(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code in (200, 503)
    body = response.json()
    assert "data" in body
    assert "checks" in body["data"]
    assert "db" in body["data"]["checks"]
