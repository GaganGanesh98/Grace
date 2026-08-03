import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.security
async def test_openapi_and_docs_disabled_in_production(production_client: AsyncClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = await production_client.get(path)
        assert response.status_code == 404, path
