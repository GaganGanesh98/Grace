from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slug: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    pack: str = Field(default="custom", max_length=64)
    rules: list[object] = Field(default_factory=list)


class PolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    pack: str | None = Field(default=None, max_length=64)
    rules: list[object] | None = None
    is_active: bool | None = None


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    slug: str
    name: str
    description: str | None
    pack: str
    version: int
    rules: list[object]
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class PolicySearchResult(BaseModel):
    """A semantically-matched policy plus its similarity to the query."""

    policy: PolicyOut
    similarity: float = Field(description="Cosine similarity to the query (1.0 = identical).")
