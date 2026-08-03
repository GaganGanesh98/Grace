import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_invite_placeholder_user_without_signup(client: AsyncClient) -> None:
    owner_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "P", "slug": unique_slug("ph-proj")},
    )
    pid = project.json()["data"]["id"]
    ghost = f"ghost-{uuid.uuid4().hex}@example.com"
    inv = await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": ghost, "role": "MEMBER"},
    )
    assert inv.status_code == 201, inv.text


@pytest.mark.asyncio
async def test_invite_and_list_members(client: AsyncClient) -> None:
    owner_email = unique_email()
    member_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    await signup_user(client, member_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "Team", "slug": unique_slug("team-proj")},
    )
    pid = project.json()["data"]["id"]
    inv = await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": member_email, "role": "MEMBER"},
    )
    assert inv.status_code == 201, inv.text

    listed = await client.get(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
    )
    assert listed.status_code == 200
    assert len(listed.json()["data"]) >= 2


@pytest.mark.asyncio
async def test_member_cannot_invite(client: AsyncClient) -> None:
    owner_email = unique_email()
    member_email = unique_email()
    extra_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    member_t = await signup_user(client, member_email, "password1a")
    await signup_user(client, extra_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "R", "slug": unique_slug("r-proj")},
    )
    pid = project.json()["data"]["id"]
    await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": member_email, "role": "MEMBER"},
    )
    response = await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(member_t["access_token"]),
        json={"email": extra_email, "role": "MEMBER"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_remove_owner(client: AsyncClient) -> None:
    owner_email = unique_email()
    admin_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    admin_t = await signup_user(client, admin_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "O", "slug": unique_slug("o-proj")},
    )
    pid = project.json()["data"]["id"]
    await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": admin_email, "role": "ADMIN"},
    )
    members = await client.get(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
    )
    owner_member_id = next(m["id"] for m in members.json()["data"] if m["role"] == "OWNER")
    response = await client.delete(
        f"/api/v1/projects/{pid}/members/{owner_member_id}",
        headers=auth_headers(admin_t["access_token"]),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_updates_member_role_and_removes(client: AsyncClient) -> None:
    owner_email = unique_email()
    admin_email = unique_email()
    member_email = unique_email()
    owner_t = await signup_user(client, owner_email, "password1a")
    admin_t = await signup_user(client, admin_email, "password1a")
    await signup_user(client, member_email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(owner_t["access_token"]),
        json={"name": "M", "slug": unique_slug("m-proj")},
    )
    pid = project.json()["data"]["id"]
    await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": admin_email, "role": "ADMIN"},
    )
    await client.post(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
        json={"email": member_email, "role": "MEMBER"},
    )
    members = await client.get(
        f"/api/v1/projects/{pid}/members",
        headers=auth_headers(owner_t["access_token"]),
    )
    member_row = next(m for m in members.json()["data"] if m["role"] == "MEMBER")
    mid = member_row["id"]
    patch = await client.patch(
        f"/api/v1/projects/{pid}/members/{mid}",
        headers=auth_headers(admin_t["access_token"]),
        json={"role": "ADMIN"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["role"] == "ADMIN"

    removed = await client.delete(
        f"/api/v1/projects/{pid}/members/{mid}",
        headers=auth_headers(owner_t["access_token"]),
    )
    assert removed.status_code == 200
