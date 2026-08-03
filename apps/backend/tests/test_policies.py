import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_policy_versioning_on_patch(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "Pol", "slug": unique_slug("pol-proj")},
    )
    pid = project.json()["data"]["id"]
    pol_slug = unique_slug("p1")
    created = await client.post(
        f"/api/v1/projects/{pid}/policies",
        headers=h,
        json={"slug": pol_slug, "name": "Policy 1", "rules": []},
    )
    assert created.status_code == 201
    policy_id = created.json()["data"]["id"]
    assert created.json()["data"]["version"] == 1

    patched = await client.patch(
        f"/api/v1/projects/{pid}/policies/{policy_id}",
        headers=h,
        json={"name": "Policy 1 v2"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["version"] == 2
    policy_id = patched.json()["data"]["id"]

    listed = await client.get(f"/api/v1/projects/{pid}/policies", headers=h)
    assert listed.status_code == 200

    got = await client.get(f"/api/v1/projects/{pid}/policies/{policy_id}", headers=h)
    assert got.status_code == 200

    deleted = await client.delete(f"/api/v1/projects/{pid}/policies/{policy_id}", headers=h)
    assert deleted.status_code == 200
