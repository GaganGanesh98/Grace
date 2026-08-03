import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_create_and_list_projects(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    headers = auth_headers(tokens["access_token"])
    slug = unique_slug("alpha-proj")
    create = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Alpha", "description": "d", "slug": slug},
    )
    assert create.status_code == 201, create.text
    project_id = create.json()["data"]["id"]

    listed = await client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    slugs = {p["slug"] for p in listed.json()["data"]}
    assert slug in slugs

    get_one = await client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert get_one.status_code == 200

    patch = await client.patch(
        f"/api/v1/projects/{project_id}",
        headers=headers,
        json={"name": "Alpha2"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["name"] == "Alpha2"


@pytest.mark.asyncio
async def test_project_forbidden_for_non_member(client: AsyncClient) -> None:
    owner_email = unique_email()
    other_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    other_t = await signup_user(client, other_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "Secret", "slug": unique_slug("secret-proj")},
    )
    pid = project.json()["data"]["id"]
    response = await client.get(
        f"/api/v1/projects/{pid}",
        headers=auth_headers(other_t["access_token"]),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_owner_only(client: AsyncClient) -> None:
    owner_email = unique_email()
    member_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    member_t = await signup_user(client, member_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "Del", "slug": unique_slug("del-proj")},
    )
    pid = project.json()["data"]["id"]
    await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": member_email, "role": "MEMBER"},
    )
    forbidden = await client.delete(
        f"/api/v1/projects/{pid}",
        headers=auth_headers(member_t["access_token"]),
    )
    assert forbidden.status_code == 403

    ok = await client.delete(
        f"/api/v1/projects/{pid}",
        headers=auth_headers(owner_t["access_token"]),
    )
    assert ok.status_code == 200
