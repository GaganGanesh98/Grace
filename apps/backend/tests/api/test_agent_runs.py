"""Phase 6.5 — /v1/agent-runs API (Batch B registers routes). RED until implemented."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.asyncio
async def test_list_agent_runs_not_404(client: AsyncClient) -> None:
    """Batch B: GET /v1/agent-runs must exist (dual auth)."""
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    r = await client.get("/v1/agent-runs", headers=h)
    assert r.status_code != 404, r.text


@pytest.mark.asyncio
async def test_create_agent_run_unknown_definition_returns_404(client: AsyncClient) -> None:
    """Missing or cross-project agent definition → 404 (no existence leak)."""
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "Runs", "slug": unique_slug("runs-proj")},
    )
    assert project.status_code == 201, project.text
    pid = project.json()["data"]["id"]
    r = await client.post(
        f"/v1/agent-runs?project_id={pid}",
        headers=h,
        json={"agent_definition_id": "00000000-0000-0000-0000-000000000001", "input": {}},
    )
    assert r.status_code == 404, r.text


async def _one_project_headers(client: AsyncClient) -> tuple[dict[str, str], str]:
    """Signup + one project; return (auth headers, project id) for JWT-scoped /v1 calls."""
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    h = auth_headers(tokens["access_token"])
    project = await client.post(
        "/api/v1/projects",
        headers=h,
        json={"name": "AR", "slug": unique_slug("ar-proj")},
    )
    assert project.status_code == 201, project.text
    pid = project.json()["data"]["id"]
    return h, pid


@pytest.mark.asyncio
async def test_get_agent_run_missing_returns_404(client: AsyncClient) -> None:
    """Missing run → 404."""
    h, pid = await _one_project_headers(client)
    rid = "00000000-0000-0000-0000-000000000099"
    r = await client.get(f"/v1/agent-runs/{rid}?project_id={pid}", headers=h)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_cancel_agent_run_missing_returns_404(client: AsyncClient) -> None:
    """POST /v1/agent-runs/{id}/cancel on unknown run → 404."""
    h, pid = await _one_project_headers(client)
    rid = "00000000-0000-0000-0000-000000000002"
    r = await client.post(f"/v1/agent-runs/{rid}/cancel?project_id={pid}", headers=h)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_agent_run_ws_token_missing_returns_404(client: AsyncClient) -> None:
    """POST /v1/agent-runs/{id}/ws-token on unknown run → 404."""
    h, pid = await _one_project_headers(client)
    rid = "00000000-0000-0000-0000-000000000003"
    r = await client.post(f"/v1/agent-runs/{rid}/ws-token?project_id={pid}", headers=h)
    assert r.status_code == 404, r.text
