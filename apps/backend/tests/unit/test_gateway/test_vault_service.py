"""Vault service unit tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from axiom.core import errors
from axiom.db import session_scope
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.project import Project
from axiom.models.vault import VaultKey
from axiom.services import auth as auth_service
from axiom.services import vault as vault_service


@pytest.mark.asyncio
async def test_store_key_encrypts() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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

        row, _detected = await vault_service.store_key(
            session,
            user.id,
            "openai",
            "Prod",
            "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789",
        )
        await session.commit()
        raw = await session.get(VaultKey, row.id)
        assert raw is not None
        assert raw.encrypted_key != b"sk-proj"


def test_detect_github_pat_returns_tool_kind() -> None:
    k, s = vault_service.detect_credential_kind_and_service("ghp_xxxxxxxxxxxxxxxxxxxx")
    assert k == "tool"
    assert s == "github"


def test_detect_slack_token_returns_tool_kind() -> None:
    k, s = vault_service.detect_credential_kind_and_service("xoxb-123-456-7890")
    assert k == "tool"
    assert s == "slack"


def test_detect_aws_key_returns_tool_kind() -> None:
    k, s = vault_service.detect_credential_kind_and_service("AKIA" + "0" * 16)
    assert k == "tool"
    assert s == "aws"


def test_detect_unknown_returns_custom_custom() -> None:
    k, s = vault_service.detect_credential_kind_and_service("totally-unknown-format")
    assert k == "custom"
    assert s == "custom"


@pytest.mark.asyncio
async def test_create_llm_key_for_user() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        row, dk, ds = await vault_service.create_vault_key(
            session, user.id, "n1", "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx"
        )
        await session.commit()
        assert dk == "llm" and ds == "anthropic"
        vk = await session.get(VaultKey, row.id)
        assert vk is not None
        assert vk.kind == "llm"
        assert vk.service == "anthropic"


@pytest.mark.asyncio
async def test_list_vault_keys_filters_by_kind() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        await vault_service.create_vault_key(session, user.id, "llm1", "sk-proj-" + "a" * 40)
        await vault_service.create_vault_key(
            session,
            user.id,
            "tool1",
            "ghp_xxxxxxxxxxxxxxxxxxxx",
            kind_override="tool",
            service_override="github",
        )
        await session.commit()
        uid = user.id

    async with session_scope() as session:
        llm_only = await vault_service.list_keys(session, uid, kind="llm")
        tool_only = await vault_service.list_keys(session, uid, kind="tool")
        assert len(llm_only) >= 1
        assert all(x.kind == "llm" for x in llm_only)
        assert len(tool_only) >= 1
        assert all(x.kind == "tool" for x in tool_only)


@pytest.mark.asyncio
async def test_delete_vault_key_in_use_returns_error() -> None:
    from axiom.models.agent import Agent
    from axiom.models.agent_definition import AgentDefinition

    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        row, _, _ = await vault_service.create_vault_key(
            session, user.id, "vk", "sk-proj-" + "z" * 40
        )
        kid = row.id
        ag = Agent(
            project_id=project.id,
            slug=f"ag-{uuid4().hex[:8]}",
            name="A",
            description=None,
            agent_type="custom",
            default_mode="shadow",
            metadata_={},
            created_by_user_id=user.id,
        )
        session.add(ag)
        await session.flush()
        session.add(
            AgentDefinition(
                project_id=project.id,
                agent_id=ag.id,
                name="Def",
                description=None,
                system_prompt=None,
                model="gpt-4o",
                vault_key_id=kid,
                tools_config={},
                created_by=user.id,
            )
        )
        await session.commit()

    async with session_scope() as session:
        with pytest.raises(errors.VaultKeyInUseError):
            await vault_service.delete_key(session, user.id, kid)


@pytest.mark.asyncio
async def test_deactivate_vault_key_succeeds_even_in_use() -> None:
    from axiom.models.agent import Agent
    from axiom.models.agent_definition import AgentDefinition

    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        row, _, _ = await vault_service.create_vault_key(
            session, user.id, "vk2", "sk-proj-" + "y" * 40
        )
        kid = row.id
        ag = Agent(
            project_id=project.id,
            slug=f"ag-{uuid4().hex[:8]}",
            name="B",
            description=None,
            agent_type="custom",
            default_mode="shadow",
            metadata_={},
            created_by_user_id=user.id,
        )
        session.add(ag)
        await session.flush()
        session.add(
            AgentDefinition(
                project_id=project.id,
                agent_id=ag.id,
                name="Def2",
                description=None,
                system_prompt=None,
                model="gpt-4o",
                vault_key_id=kid,
                tools_config={},
                created_by=user.id,
            )
        )
        await session.commit()

    async with session_scope() as session:
        d = await vault_service.deactivate_vault_key(session, user.id, kid)
        assert d.is_active is False


@pytest.mark.asyncio
async def test_store_key_auto_detects_provider() -> None:
    k, s = vault_service.detect_credential_kind_and_service("sk-ant-api03")
    assert k == "llm" and s == "anthropic"


@pytest.mark.asyncio
async def test_get_key_decrypts_correctly() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        secret = "sk-proj-abc123456789012345678901234567890"
        await vault_service.store_key(session, user.id, "openai", "K1", secret)
        await session.commit()
        uid = user.id

    async with session_scope() as session:
        got = await vault_service.get_key_for_provider(session, uid, "openai")
        assert got == secret


@pytest.mark.asyncio
async def test_list_keys_never_returns_raw_key() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        await vault_service.store_key(session, user.id, "openai", "K2", "sk-proj-abcdefghijklmnop")
        await session.commit()
        uid = user.id

    async with session_scope() as session:
        rows = await vault_service.list_keys(session, uid)
        assert len(rows) >= 1
        s = str(rows[0].__dict__)
        assert "sk-proj-abcdefghijklmnop" not in s


@pytest.mark.asyncio
async def test_delete_key_removes_from_db() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        row, _ = await vault_service.store_key(session, user.id, "openai", "K3", "sk-proj-xyz")
        kid = row.id
        await session.commit()

    async with session_scope() as session:
        await vault_service.delete_key(session, user.id, kid)
        await session.commit()

    async with session_scope() as session:
        assert await session.get(VaultKey, kid) is None


@pytest.mark.asyncio
async def test_get_nonexistent_provider_returns_none() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        await session.commit()
        uid = user.id

    async with session_scope() as session:
        assert await vault_service.get_key_for_provider(session, uid, "xai") is None


def test_key_prefix_suffix_extracted_correctly() -> None:
    raw = "sk-proj-abcdefghijklmnop"
    assert vault_service._display_prefix(raw).startswith("sk-proj-")
    assert vault_service._display_suffix(raw).endswith("mnop")


@pytest.mark.asyncio
async def test_duplicate_provider_name_rejected() -> None:
    email = f"vault-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(session, email=email, password="password1a", full_name="T")
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
        await vault_service.store_key(session, user.id, "openai", "Dup", "sk-proj-aaaaaaaaaaaaaaaaaaaa")
        uid = user.id
        await session.commit()

    async with session_scope() as session:
        with pytest.raises(errors.ConflictError):
            await vault_service.store_key(session, uid, "openai", "Dup", "sk-proj-bbbbbbbbbbbbbbbbbbbb")
