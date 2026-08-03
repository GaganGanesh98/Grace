import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
@pytest.mark.security
async def test_per_page_above_cap_returns_422(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "P", "slug": unique_slug("pag-proj")},
    )
    assert project.status_code == 201
    pid = project.json()["data"]["id"]
    response = await client.get(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(tokens["access_token"]),
        params={"page": 1, "per_page": 10000},
    )
    assert response.status_code == 422
