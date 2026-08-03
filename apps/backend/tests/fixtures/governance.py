"""Shared helpers for Phase 2 governance tests.

Provides: create a project, seed a policy, mint an API key — all via the
normal HTTP surface so tests exercise the same code paths real clients do.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


async def bootstrap_project_with_api_key(
    client: AsyncClient,
    *,
    policy_rules: list[dict[str, Any]] | None = None,
    agent_name: str = "agent-1",
) -> dict[str, str]:
    """Create user + project + policy + agent + API key. Return a dict of ids
    and the full API key string.

    Keys returned:
      user_access, project_id, policy_id, policy_slug, agent_id,
      api_key_id, api_key_full
    """

    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    access = tokens["access_token"]
    h = auth_headers(access)

    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "Test", "slug": unique_slug("gov-proj")},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["data"]["id"]

    pol_slug = unique_slug("pol")
    pol_body: dict[str, Any] = {
        "slug": pol_slug,
        "name": "Test Policy",
        "rules": policy_rules if policy_rules is not None else [],
    }
    policy = await client.post(
        f"/api/v1/projects/{project_id}/policies",
        headers=h,
        json=pol_body,
    )
    assert policy.status_code == 201, policy.text
    policy_id = policy.json()["data"]["id"]

    agent = await client.post(
        f"/api/v1/projects/{project_id}/agents",
        headers=h,
        json={
            "name": agent_name,
            "slug": unique_slug(agent_name),
            "default_mode": "shadow",
        },
    )
    assert agent.status_code == 201, agent.text
    agent_id = agent.json()["data"]["id"]

    key = await client.post(
        f"/api/v1/projects/{project_id}/api-keys",
        headers=h,
        json={"name": "testkey", "scopes": ["govern:write"]},
    )
    assert key.status_code == 201, key.text
    kid = key.json()["data"]["id"]
    full_key = key.json()["data"]["full_key"]

    return {
        "user_access": access,
        "project_id": project_id,
        "policy_id": policy_id,
        "policy_slug": pol_slug,
        "agent_id": agent_id,
        "api_key_id": kid,
        "api_key_full": full_key,
    }
