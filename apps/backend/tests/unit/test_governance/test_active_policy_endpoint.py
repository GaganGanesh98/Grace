"""GET /v1/governance/policies/active — config-based policy without receipts."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from axiom.db import session_scope
from axiom.models.project import Project
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key

G_PREFIX = "/v1/governance"


@pytest.mark.asyncio
async def test_active_policy_default_without_receipts(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.get(
        f"{G_PREFIX}/policies/active",
        headers=auth_headers(fx["user_access"]),
        params={"project_id": fx["project_id"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "starter-safe"
    assert body["is_default_configuration"] is True
    assert isinstance(body["rules"], list)
    assert len(body["rules"]) >= 1


@pytest.mark.asyncio
async def test_active_policy_reflects_project_settings(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        await session.execute(
            update(Project).where(Project.id == pid).values(settings={"governance_policy": "approval-first"})
        )
        await session.commit()

    r = await client.get(
        f"{G_PREFIX}/policies/active",
        headers=auth_headers(fx["user_access"]),
        params={"project_id": fx["project_id"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "approval-first"
    assert body["is_default_configuration"] is False


@pytest.mark.asyncio
async def test_active_policy_with_api_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.get(
        f"{G_PREFIX}/policies/active",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "starter-safe"
