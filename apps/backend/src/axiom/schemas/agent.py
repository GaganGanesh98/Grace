from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slug: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    agent_type: str = Field(default="custom", max_length=64)
    default_mode: str = Field(default="shadow", pattern="^(enforce|shadow|audit)$")
    metadata_: dict[str, object] = Field(
        default_factory=dict,
        serialization_alias="metadata",
        validation_alias="metadata",
    )


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    agent_type: str | None = Field(default=None, max_length=64)
    default_mode: str | None = Field(default=None, pattern="^(enforce|shadow|audit)$")
    metadata_: dict[str, object] | None = Field(
        default=None,
        serialization_alias="metadata",
        validation_alias="metadata",
    )
    is_active: bool | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    project_id: UUID
    slug: str
    name: str
    description: str | None
    agent_type: str
    default_mode: str
    metadata_: dict[str, object] = Field(serialization_alias="metadata")
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
