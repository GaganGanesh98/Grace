import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_agent_crud(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "P", "slug": unique_slug("agent-proj")},
    )
    pid = project.json()["data"]["id"]
    bot_slug = unique_slug("bot-a")
    created = await client.post(
        f"/api/v1/projects/{pid}/agents",
        headers=h,
        json={
            "slug": bot_slug,
            "name": "Bot A",
            "description": None,
            "agent_type": "custom",
            "default_mode": "shadow",
            "metadata": {},
        },
    )
    assert created.status_code == 201, created.text
    aid = created.json()["data"]["id"]

    dup = await client.post(
        f"/api/v1/projects/{pid}/agents",
        headers=h,
        json={
            "slug": bot_slug,
            "name": "Dup",
            "description": None,
            "agent_type": "custom",
            "default_mode": "audit",
            "metadata": {},
        },
    )
    assert dup.status_code == 409

    listed = await client.get(f"/api/v1/projects/{pid}/agents", headers=h)
    assert listed.status_code == 200
    assert any(row["id"] == aid for row in listed.json()["data"])

    got = await client.get(f"/api/v1/projects/{pid}/agents/{aid}", headers=h)
    assert got.status_code == 200

    patched = await client.patch(
        f"/api/v1/projects/{pid}/agents/{aid}",
        headers=h,
        json={"name": "Renamed Bot", "is_active": True},
    )
    assert patched.status_code == 200

    deleted = await client.delete(f"/api/v1/projects/{pid}/agents/{aid}", headers=h)
    assert deleted.status_code == 200
