"""Command Center aggregate DTOs (Phase 7.5.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CryptoSigningStatus = Literal["all_signed", "partial", "never_signed", "no_data"]
MerkleStatus = Literal["healthy", "no_data"]


class PostureOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    calls_governed: int = Field(ge=0)
    runs_completed: int = Field(ge=0)
    violations: int = Field(ge=0)


class CryptoHealthOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    ed25519_status: CryptoSigningStatus
    mldsa65_status: CryptoSigningStatus
    merkle_status: MerkleStatus
    next_rotation_days: int | None = None


class PolicyBreakdownOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_name: str | None
    evaluated_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    escalated_count: int = Field(ge=0)
    denied_count: int = Field(ge=0)


class TsaStatusOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    last_anchor_age_seconds: int | None
    tsa_authority_url: str | None
