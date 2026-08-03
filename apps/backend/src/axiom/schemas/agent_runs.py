"""Request/response models for /v1/agent-runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_definition_id: UUID
    input: dict[str, Any] = Field(default_factory=dict)


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    agent_definition_id: UUID
    status: str
    correlation_id: str
    input_payload: dict[str, Any] | None
    final_output: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    receipt_ids: list[Any] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AgentRunWsTokenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    token: str
    expires_in_seconds: int = 300
