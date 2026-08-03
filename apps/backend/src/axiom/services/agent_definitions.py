"""CRUD for `agent_definitions` (Phase 6.5)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.models.agent import Agent
from axiom.models.agent_definition import AgentDefinition
from axiom.models.vault import VaultKey
from axiom.services import agents as agents_service
from axiom.services import audit as audit_service

SUPPORTED_PROVIDERS = frozenset({"openai", "anthropic", "google", "groq", "xai"})


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "definition"


def _unsupported_provider_message(provider: str) -> str:
    return (
        f"Provider '{provider}' is not yet supported by the agent runner. "
        "Supported providers: openai, anthropic, google, groq, xai. "
        "Additional providers are scheduled for Phase 6.7."
    )


class AgentDefinitionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        model: str,
        vault_key_id: UUID,
        created_by_user_id: UUID,
        description: str | None = None,
        system_prompt: str | None = None,
        tools_config: dict[str, object] | None = None,
        max_iterations: int | None = None,
        max_tokens_per_run: int | None = None,
    ) -> AgentDefinition:
        vk = await self._session.get(VaultKey, vault_key_id)
        if vk is None or vk.user_id != created_by_user_id:
            raise errors.ProjectNotFoundError("Vault key not found.")

        if vk.kind != "llm":
            raise errors.ValidationError("Agent vault key must be an LLM credential")

        if vk.service not in SUPPORTED_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_unsupported_provider_message(vk.service),
            )

        slug = _slugify(name)
        existing_id = await self._session.scalar(
            select(Agent.id).where(
                Agent.project_id == project_id,
                Agent.slug == slug,
                Agent.deleted_at.is_(None),
            )
        )
        if existing_id is None:
            ag = await agents_service.create_agent(
                self._session,
                project_id=project_id,
                slug=slug,
                name=name,
                description=description,
                agent_type="custom",
                default_mode="shadow",
                metadata={},
                created_by_user_id=created_by_user_id,
            )
            agent_id = ag.id
        else:
            agent_id = existing_id

        row = AgentDefinition(
            project_id=project_id,
            agent_id=agent_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            model=model,
            vault_key_id=vault_key_id,
            tools_config=tools_config if tools_config is not None else {},
            max_iterations=max_iterations if max_iterations is not None else 10,
            max_tokens_per_run=max_tokens_per_run if max_tokens_per_run is not None else 100_000,
            created_by=created_by_user_id,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise errors.ConflictError(
                "An agent definition with this name already exists.",
            ) from exc

        await audit_service.record_event(
            self._session,
            event_type="agent_definition.created",
            actor_user_id=created_by_user_id,
            project_id=project_id,
            target_type="agent_definition",
            target_id=row.id,
            metadata={"name": name},
        )
        return row

    async def get(self, *, project_id: UUID, definition_id: UUID) -> AgentDefinition:
        row = await self._session.scalar(
            select(AgentDefinition).where(
                AgentDefinition.id == definition_id,
                AgentDefinition.project_id == project_id,
            )
        )
        if row is None:
            raise errors.ProjectNotFoundError("Agent definition not found.")
        return row

    async def list(
        self, *, project_id: UUID, offset: int = 0, limit: int = 50, include_archived: bool = False
    ) -> tuple[list[AgentDefinition], int]:
        cond = [AgentDefinition.project_id == project_id]
        if not include_archived:
            cond.append(AgentDefinition.is_archived.is_(False))
        wc = and_(*cond) if len(cond) > 1 else cond[0]
        total = int(
            await self._session.scalar(select(func.count()).select_from(AgentDefinition).where(wc))
            or 0
        )
        rows = await self._session.scalars(
            select(AgentDefinition)
            .where(wc)
            .order_by(AgentDefinition.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows), total

    async def update(
        self,
        row: AgentDefinition,
        *,
        actor_user_id: UUID | None = None,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        vault_key_id: UUID | None = None,
        tools_config: dict[str, object] | None = None,
        max_iterations: int | None = None,
        max_tokens_per_run: int | None = None,
    ) -> AgentDefinition:
        vault_owner_id = actor_user_id if actor_user_id is not None else row.created_by
        if vault_key_id is not None:
            vk = await self._session.get(VaultKey, vault_key_id)
            if vk is None or vk.user_id != vault_owner_id:
                raise errors.ProjectNotFoundError("Vault key not found.")
            if vk.kind != "llm":
                raise errors.ValidationError("Agent vault key must be an LLM credential")
            if vk.service not in SUPPORTED_PROVIDERS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_unsupported_provider_message(vk.service),
                )
            row.vault_key_id = vault_key_id

        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if system_prompt is not None:
            row.system_prompt = system_prompt
        if model is not None:
            row.model = model
        if tools_config is not None:
            row.tools_config = tools_config
        if max_iterations is not None:
            row.max_iterations = max_iterations
        if max_tokens_per_run is not None:
            row.max_tokens_per_run = max_tokens_per_run
        return row

    async def archive(self, row: AgentDefinition) -> AgentDefinition:
        row.is_archived = True
        return row
