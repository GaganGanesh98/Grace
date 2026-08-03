import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
@pytest.mark.security
async def test_non_member_get_project_returns_404(client: AsyncClient) -> None:
    owner_email = unique_email()
    other_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    other_t = await signup_user(client, other_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "Secret", "slug": unique_slug("bola-proj")},
    )
    pid = project.json()["data"]["id"]
    response = await client.get(
        f"/api/v1/projects/{pid}",
        headers=auth_headers(other_t["access_token"]),
    )
    assert response.status_code == 404
