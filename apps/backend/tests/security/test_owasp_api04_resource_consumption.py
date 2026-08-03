"""API4 — maps to body size, pagination, and rate limit tests in sibling modules."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
@pytest.mark.security
async def test_per_page_validation_enforced(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "R", "slug": unique_slug("res-proj")},
    )
    pid = project.json()["data"]["id"]
    response = await client.get(
        f"/api/v1/projects/{pid}/agents",
        headers=auth_headers(tokens["access_token"]),
        params={"per_page": 9999},
    )
    assert response.status_code == 422
