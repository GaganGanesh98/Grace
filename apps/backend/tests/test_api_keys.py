import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_api_key_create_list_revoke(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "K", "slug": unique_slug("key-proj")},
    )
    pid = project.json()["data"]["id"]
    created = await client.post(
        f"/api/v1/projects/{pid}/api-keys",
        headers=h,
        json={"name": "k1", "scopes": ["govern:write"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert "full_key" in body
    assert isinstance(body["full_key"], str)
    kid = body["id"]

    listed = await client.get(f"/api/v1/projects/{pid}/api-keys", headers=h)
    assert listed.status_code == 200
    for row in listed.json()["data"]:
        assert "full_key" not in row
        assert "key_hash" not in row

    revoked = await client.delete(f"/api/v1/projects/{pid}/api-keys/{kid}", headers=h)
    assert revoked.status_code == 200
