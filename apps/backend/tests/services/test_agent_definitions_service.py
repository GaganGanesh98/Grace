"""AgentDefinitionService — legacy ``agents`` bridge and provider validation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from axiom.db import session_scope
from axiom.models.agent import Agent
from axiom.models.agent_definition import AgentDefinition
from axiom.services import agents as agents_service
from axiom.services import auth as auth_service
from axiom.services import projects as projects_service
from axiom.services import vault as vault_service
from axiom.services.agent_definitions import AgentDefinitionService


def _expected_replicate_message() -> str:
    return (
        "Provider 'replicate' is not yet supported by the agent runner. "
        "Supported providers: openai, anthropic, google, groq, xai. "
        "Additional providers are scheduled for Phase 6.7."
    )


async def _seed_user_and_project() -> tuple[UUID, UUID]:
    email = f"ad-svc-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _acc, _ref = await auth_service.signup(
            session,
            email=email,
            password="password1a",
            full_name="AD Test",
        )
        project = await projects_service.create_project(
            session,
            owner=user,
            name="AD Project",
            description=None,
            slug=f"ad-proj-{uuid4().hex[:10]}",
        )
        uid, pid = user.id, project.id
    return uid, pid


@pytest.mark.asyncio
async def test_create_definition_creates_matching_legacy_agent() -> None:
    user_id, project_id = await _seed_user_and_project()
    async with session_scope() as session:
        vk, _ = await vault_service.store_key(
            session,
            user_id,
            None,
            "openai-key",
            "sk-proj-" + "a" * 40,
        )
        n_agents_before = int(
            await session.scalar(
                select(func.count()).select_from(Agent).where(
                    Agent.project_id == project_id,
                    Agent.deleted_at.is_(None),
                )
            )
            or 0
        )
        assert n_agents_before == 0

        svc = AgentDefinitionService(session)
        definition = await svc.create(
            project_id=project_id,
            name="Alpha Bot",
            model="gpt-4o",
            vault_key_id=vk.id,
            created_by_user_id=user_id,
            tools_config={},
        )
        await session.flush()

        row_ad = await session.get(AgentDefinition, definition.id)
        assert row_ad is not None
        assert row_ad.name == "Alpha Bot"

        ag = await session.scalar(
            select(Agent).where(
                Agent.project_id == project_id,
                Agent.slug == "alpha-bot",
                Agent.deleted_at.is_(None),
            )
        )
        assert ag is not None
        assert row_ad.agent_id == ag.id

        n_agents_after = int(
            await session.scalar(
                select(func.count()).select_from(Agent).where(
                    Agent.project_id == project_id,
                    Agent.deleted_at.is_(None),
                )
            )
            or 0
        )
        assert n_agents_after == 1


@pytest.mark.asyncio
async def test_create_definition_reuses_existing_legacy_agent() -> None:
    user_id, project_id = await _seed_user_and_project()
    async with session_scope() as session:
        vk, _ = await vault_service.store_key(
            session,
            user_id,
            None,
            "openai-key-2",
            "sk-proj-" + "b" * 40,
        )
        existing = await agents_service.create_agent(
            session,
            project_id=project_id,
            slug="my-bot",
            name="My Bot",
            description=None,
            agent_type="custom",
            default_mode="shadow",
            metadata={},
            created_by_user_id=user_id,
        )
        await session.flush()
        count_before = int(
            await session.scalar(
                select(func.count()).select_from(Agent).where(
                    Agent.project_id == project_id,
                    Agent.deleted_at.is_(None),
                )
            )
            or 0
        )

        svc = AgentDefinitionService(session)
        definition = await svc.create(
            project_id=project_id,
            name="my-bot",
            model="gpt-4o",
            vault_key_id=vk.id,
            created_by_user_id=user_id,
            tools_config={},
        )
        await session.flush()

        count_after = int(
            await session.scalar(
                select(func.count()).select_from(Agent).where(
                    Agent.project_id == project_id,
                    Agent.deleted_at.is_(None),
                )
            )
            or 0
        )
        assert count_before == count_after
        assert definition.agent_id == existing.id


@pytest.mark.asyncio
async def test_create_definition_rejects_unsupported_provider() -> None:
    user_id, project_id = await _seed_user_and_project()
    async with session_scope() as session:
        vk, _ = await vault_service.store_key(
            session,
            user_id,
            None,
            "rep-key",
            "r8_" + "a" * 32,
        )
        svc = AgentDefinitionService(session)
        with pytest.raises(HTTPException) as exc_info:
            await svc.create(
                project_id=project_id,
                name="Replicate Bot",
                model="any",
                vault_key_id=vk.id,
                created_by_user_id=user_id,
                tools_config={},
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == _expected_replicate_message()


@pytest.mark.asyncio
async def test_list_omits_archived_definitions_by_default() -> None:
    """Non-archived filter matches router list + projects-page count (B3 wrong-source diagnosis: bridge OK)."""
    user_id, project_id = await _seed_user_and_project()
    async with session_scope() as session:
        vk, _ = await vault_service.store_key(
            session,
            user_id,
            None,
            "openai-key-arch",
            "sk-proj-" + "c" * 40,
        )
        svc = AgentDefinitionService(session)
        row = await svc.create(
            project_id=project_id,
            name="Archivable",
            model="gpt-4o",
            vault_key_id=vk.id,
            created_by_user_id=user_id,
            tools_config={},
        )
        await session.flush()
        _rows1, total1 = await svc.list(project_id=project_id)
        assert total1 == 1
        await svc.archive(row)
        await session.flush()
        rows2, total2 = await svc.list(project_id=project_id)
        assert total2 == 0
        assert len(rows2) == 0
        rows3, total3 = await svc.list(project_id=project_id, include_archived=True)
        assert total3 == 1
        assert len(rows3) == 1
        assert rows3[0].is_archived is True
