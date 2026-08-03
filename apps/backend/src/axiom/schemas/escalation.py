"""Schemas for the n8n escalation flow (outbound payload + inbound callback)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EscalationDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED_TO_HUMAN = "escalated_to_human"


class EscalationAction(BaseModel):
    type: str
    target: str
    parameters: dict[str, object] = Field(default_factory=dict)


class EscalationPolicy(BaseModel):
    policy_version: str
    rule_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


class EscalationPayload(BaseModel):
    """Structured payload POSTed to the n8n webhook when an action is escalated."""

    event: str = "policy.escalation"
    receipt_id: UUID
    project_id: UUID
    agent_id: str
    action: EscalationAction
    policy_violated: EscalationPolicy
    verdict: str
    severity: str
    timestamp: datetime
    expires_at: datetime | None = None
    link: str = Field(description="Link back to the receipt record in Axiom.")
    callback_url: str = Field(description="Where n8n POSTs its decision back.")


class EscalationCallbackRequest(BaseModel):
    """Body n8n sends back to /webhooks/n8n/escalation-result."""

    model_config = ConfigDict(extra="forbid")

    receipt_id: UUID
    decision: EscalationDecision
    reason: str | None = Field(default=None, max_length=500)


class EscalationCallbackResponse(BaseModel):
    receipt_id: UUID
    approval_status: str
