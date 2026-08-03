"""Vault key DELETE — 200 response, FK guard (409), integrity safety net."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from axiom.core import errors
from axiom.db import session_scope
from axiom.models.vault import VaultKey
from axiom.services import vault as vault_service
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.mark.asyncio
async def test_delete_unreferenced_key_returns_200(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    c = await client.post(
        "/api/v1/vault",
        headers=h,
        json={
            "raw_key": "sk-proj-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "name": "Del200",
        },
    )
    assert c.status_code == 201, c.text
    kid = c.json()["id"]
    d = await client.delete(f"/api/v1/vault/{kid}", headers=h)
    assert d.status_code == 200
    data = d.json()
    assert data["deleted"] is True
    assert data["id"] == kid


@pytest.mark.asyncio
async def test_delete_unreferenced_key_removes_from_db(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    c = await client.post(
        "/api/v1/vault",
        headers=h,
        json={
            "raw_key": "sk-proj-cccccccccccccccccccccccccccccccc",
            "name": "DelDb",
        },
    )
    kid = UUID(c.json()["id"])
    d = await client.delete(f"/api/v1/vault/{kid}", headers=h)
    assert d.status_code == 200

    async with session_scope() as session:
        assert await session.get(VaultKey, kid) is None


@pytest.mark.asyncio
async def test_delete_referenced_key_returns_409(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    pid = fx["project_id"]
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "d" * 40, "name": "vk409"},
    )
    assert vk.status_code == 201, vk.text
    vault_key_id = vk.json()["id"]
    ad = await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "blocking-bot",
            "model": "gpt-4o",
            "vault_key_id": vault_key_id,
            "system_prompt": "x",
            "tools_config": {},
        },
    )
    assert ad.status_code == 201, ad.text
    d = await client.delete(f"/api/v1/vault/{vault_key_id}", headers=h)
    assert d.status_code == 409
    err = d.json()
    assert err["error"]["code"] == "vault_key_in_use"


@pytest.mark.asyncio
async def test_delete_referenced_key_preserves_key(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    pid = fx["project_id"]
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "e" * 40, "name": "vkkeep"},
    )
    vault_key_id = UUID(vk.json()["id"])
    await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "keeper",
            "model": "gpt-4o",
            "vault_key_id": str(vault_key_id),
            "system_prompt": "x",
            "tools_config": {},
        },
    )
    d = await client.delete(f"/api/v1/vault/{vault_key_id}", headers=h)
    assert d.status_code == 409

    async with session_scope() as session:
        assert await session.get(VaultKey, vault_key_id) is not None


@pytest.mark.asyncio
async def test_409_response_includes_agent_names(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    pid = fx["project_id"]
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "f" * 40, "name": "vknames"},
    )
    vault_key_id = vk.json()["id"]
    await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "named-agent",
            "model": "gpt-4o",
            "vault_key_id": vault_key_id,
            "system_prompt": "x",
            "tools_config": {},
        },
    )
    d = await client.delete(f"/api/v1/vault/{vault_key_id}", headers=h)
    assert d.status_code == 409
    agents = d.json()["error"]["details"]["referencing_agents"]
    names = [a["name"] for a in agents]
    assert "named-agent" in names


@pytest.mark.asyncio
async def test_409_response_includes_agent_ids(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    pid = fx["project_id"]
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "g" * 40, "name": "vkids"},
    )
    vault_key_id = vk.json()["id"]
    created = await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "id-agent",
            "model": "gpt-4o",
            "vault_key_id": vault_key_id,
            "system_prompt": "x",
            "tools_config": {},
        },
    )
    assert created.status_code == 201, created.text
    expected_id = created.json()["data"]["id"]
    d = await client.delete(f"/api/v1/vault/{vault_key_id}", headers=h)
    assert d.status_code == 409
    agents = d.json()["error"]["details"]["referencing_agents"]
    assert len(agents) >= 1
    match = next((a for a in agents if a["name"] == "id-agent"), None)
    assert match is not None
    assert match["id"] == expected_id


@pytest.mark.asyncio
async def test_delete_nonexistent_key_returns_404(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    h = auth_headers(fx["user_access"])
    bad_id = str(uuid4())
    d = await client.delete(f"/api/v1/vault/{bad_id}", headers=h)
    assert d.status_code == 404


@pytest.mark.asyncio
async def test_integrity_error_returns_409_not_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate FK failure on flush (race): must raise VaultKeyInUseError, not propagate 500."""
    email = f"vault-int-{uuid4().hex}@example.com"
    async with session_scope() as session:
        from axiom.models.member import MemberRole, ProjectMember
        from axiom.models.project import Project
        from axiom.services import auth as auth_service

        user, _, _ = await auth_service.signup(
            session,
            email=email,
            password="password1a",
            full_name="T",
        )
        project = await session.scalar(select(Project).where(Project.owner_user_id == user.id))
        if project is None:
            slug = f"v-{uuid4().hex}"
            project = Project(slug=slug, name="T", description=None, owner_user_id=user.id)
            session.add(project)
            await session.flush()
            session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    role=MemberRole.OWNER.value,
                    invited_by_user_id=None,
                )
            )
            await session.flush()
        row, _ = await vault_service.store_key(
            session,
            user.id,
            "openai",
            "IntKey",
            "sk-proj-" + "h" * 40,
        )
        kid = row.id
        await session.commit()

    async with session_scope() as session:
        row2 = await session.get(VaultKey, kid)
        assert row2 is not None
        first = True
        real_flush = session.flush

        async def flaky_flush() -> None:
            nonlocal first
            if first:
                first = False
                raise IntegrityError("stmt", {}, Exception("mock_orig"))
            return await real_flush()

        monkeypatch.setattr(session, "flush", flaky_flush)

        with pytest.raises(errors.VaultKeyInUseError):
            await vault_service.delete_key(session, user.id, kid)
