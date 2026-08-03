import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
@pytest.mark.security
async def test_member_cannot_create_api_key(client: AsyncClient) -> None:
    owner_email = unique_email()
    member_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    member_t = await signup_user(client, member_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "B", "slug": unique_slug("bfla-proj")},
    )
    pid = project.json()["data"]["id"]
    await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": member_email, "role": "MEMBER"},
    )
    response = await client.post(
        f"/api/v1/projects/{pid}/api-keys",
        headers=auth_headers(member_t["access_token"]),
        json={"name": "k1"},
    )
    assert response.status_code == 403
