import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
@pytest.mark.security
async def test_patch_me_rejects_privileged_fields(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(tokens["access_token"]),
        json={"full_name": "X", "role": "ADMIN"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.security
async def test_me_response_has_no_password_hash(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    response = await client.get("/api/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert "password_hash" not in response.text


@pytest.mark.asyncio
@pytest.mark.security
async def test_api_key_list_excludes_sensitive_hashes(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "K", "slug": unique_slug("key-proj")},
    )
    pid = project.json()["data"]["id"]
    response = await client.get(
        f"/api/v1/projects/{pid}/api-keys",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    for row in response.json()["data"]:
        assert "key_hash" not in row
