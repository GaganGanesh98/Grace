"""Pydantic schemas for /v1/preflight request/response.

Match governance.py conventions — Pydantic v2, extra='forbid', typed fields.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axiom.services.pipeline.protocols import PipelineMode
from axiom.services.policy.evaluator import Verdict
from axiom.services.preflight.confidence import PreflightConfidence

_PREFLIGHT_DISCLAIMER = (
    "Pre-flight is a prediction, not a governance decision. "
    "To commit an action and receive a cryptographic receipt, call POST /v1/govern."
)


class PreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: dict[str, Any] = Field(
        ...,
        description="Tentative action to pre-check. Same shape as /v1/govern action.",
    )
    agent_id: UUID
    mode: PipelineMode = Field(
        default=PipelineMode.ENFORCE,
        description=(
            "The mode the final /v1/govern call will use. Affects prediction "
            "(shadow mode in govern never blocks)."
        ),
    )
    include_related_policies: bool = Field(
        default=False,
        description=(
            "If true, attach semantically-related policies (pgvector similarity to the "
            "action) as advisory context. Off by default so the hot path stays cheap; "
            "purely additive — never affects the predicted verdict."
        ),
    )


class RelatedPolicy(BaseModel):
    """A policy semantically similar to the action, surfaced as advisory context."""

    policy_id: UUID
    slug: str
    name: str
    version: int
    similarity: float = Field(description="Cosine similarity to the action (1.0 = identical).")


class PreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction_id: str = Field(
        ...,
        description=(
            "Unique id for this pre-flight prediction. NOT a receipt. No cryptographic commitment."
        ),
    )
    predicted_verdict: Verdict = Field(
        ...,
        description="The likely verdict if you called /v1/govern with this action now.",
    )
    rule_id: str | None = Field(
        None,
        description="Matched rule id. None if default verdict was hit or pre-flight failed.",
    )
    policy_id: str
    policy_version: str
    reasoning: str
    explanation: str = Field(
        ...,
        description="Human-readable explanation with legal citations where available.",
    )
    probably_definitive: bool = Field(
        ...,
        description=(
            "True when the matched rule is deterministic "
            "(only uses eq/ne/in/not_in operators). "
            "False when the rule depends on runtime context "
            "(gt/lt — may evaluate differently later). "
            "When False, the actual /v1/govern verdict may differ from this prediction."
        ),
    )
    confidence: PreflightConfidence = Field(
        ...,
        description=(
            "HIGH: fresh computation on deterministic rule. "
            "MEDIUM: fresh computation on non-deterministic rule OR cached result <30min old. "
            "LOW: cached result >=30min old."
        ),
    )
    cached: bool
    cache_age_seconds: int | None = Field(
        None,
        description="Age of cached prediction in seconds. None when cached=False.",
    )
    correlation_id: str = Field(..., description="For request tracing. Not a receipt id.")
    related_policies: list[RelatedPolicy] = Field(
        default_factory=list,
        description=(
            "Advisory: policies semantically similar to the action (pgvector). "
            "Empty unless include_related_policies was requested. Does not affect the verdict."
        ),
    )
    disclaimer: str = Field(
        default=_PREFLIGHT_DISCLAIMER,
        description="Reminder that this response is a prediction, not a receipt.",
    )
