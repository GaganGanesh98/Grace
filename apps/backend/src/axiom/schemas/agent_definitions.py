"""Request/response models for /v1/agent-definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentDefinitionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_archived: bool | None = None


class AgentDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=500)
    model: str = Field(..., min_length=1, max_length=1024)
    vault_key_id: UUID
    description: str | None = None
    system_prompt: str | None = None
    tools_config: dict[str, Any] = Field(default_factory=dict)
    max_iterations: int | None = Field(default=None, ge=1, le=1000)
    max_tokens_per_run: int | None = Field(default=None, ge=1, le=10_000_000)


class AgentDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    agent_id: UUID
    name: str
    description: str | None
    system_prompt: str | None
    model: str
    vault_key_id: UUID
    tools_config: dict[str, Any]
    max_iterations: int
    max_tokens_per_run: int
    is_archived: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime
