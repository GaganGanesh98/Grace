"""Vault API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VaultKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_key: str = Field(..., min_length=1, max_length=8192)
    name: str = Field(..., min_length=1, max_length=100)
    service_override: str | None = Field(None, max_length=50)
    kind_override: str | None = Field(None, max_length=16)


class VaultKeyCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: str
    service: str
    name: str
    key_prefix: str
    key_suffix: str
    detected_kind: str
    detected_service: str
    created_at: datetime


class VaultKeyListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: str
    service: str
    name: str
    key_prefix: str
    key_suffix: str
    is_active: bool
    created_at: datetime


class VaultKeyDeletedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool = True
    id: UUID


class VaultKeyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class VaultDetectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_key: str = Field(..., min_length=1, max_length=8192)


class VaultDetectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    service: str
