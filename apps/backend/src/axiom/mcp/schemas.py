"""Pydantic models for MCP tool inputs and outputs.

Strict (``extra="forbid"``) in both directions, matching
``axiom.schemas.governance``: an accidental field leak should fail loudly in
CI rather than ship.

These deliberately mirror the HTTP schemas rather than inventing a parallel
vocabulary. An agent that has read Grace's REST docs should recognise every
field name here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axiom.services.pipeline.protocols import PipelineMode
from axiom.services.policy.evaluator import Verdict


class GovernActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: dict[str, Any] = Field(
        ...,
        description=(
            "The action the agent intends to take, as a JSON object. Shape is "
            "policy-defined; commonly includes keys such as 'type', 'target', "
            "and 'parameters'."
        ),
    )
    agent_id: UUID = Field(
        ...,
        description="UUID of the registered agent taking this action.",
    )
    mode: PipelineMode = Field(
        default=PipelineMode.ENFORCE,
        description=(
            "'enforce' blocks on deny/escalate. 'shadow' observes and records a "
            "receipt without ever blocking — use it to trial a policy."
        ),
    )


class GovernActionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(
        ...,
        description="Plain-language statement of the verdict. Read this first.",
    )
    verdict: Verdict
    allowed: bool = Field(
        ...,
        description="True only when the agent may proceed with the action as submitted.",
    )
    reasoning: str
    explanation: str
    modification: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Present when verdict is 'modify'. The agent MUST substitute this "
            "for its original action."
        ),
    )
    escalation_target: str | None = None
    receipt_id: str
    execution_id: str
    verify_url: str
    merkle_leaf_index: int
    merkle_tree_size: int
    merkle_root: str
    algorithm: str
    signed_at: datetime
    dispatched: bool
    correlation_id: str


class CheckPolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: dict[str, Any] = Field(
        ...,
        description="The prospective action to evaluate, same shape as govern_action.",
    )
    policy_id: UUID | None = Field(
        default=None,
        description=(
            "Optional specific policy to evaluate against. Defaults to the project's active policy."
        ),
    )


class CheckPolicyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    verdict: Verdict
    allowed: bool
    reasoning: str
    rule_id: str | None
    policy_id: str
    policy_version: str
    modification: dict[str, Any] | None = None
    escalation_target: str | None = None
    is_audit_record: bool = Field(
        default=False,
        description=(
            "Always false. check_policy is a dry run: it creates no receipt and "
            "is not an audit record. Call govern_action for a signed record."
        ),
    )


class VerifyReceiptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str


class VerificationChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ed25519_signature_valid: bool
    ml_dsa_signature_valid: bool
    merkle_inclusion_valid: bool
    payload_hash_matches: bool


class VerifyReceiptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., description="Plain-language verification result.")
    receipt_id: str
    verified: bool
    algorithm: str
    signed_at: datetime
    payload_hash: str
    merkle_root: str
    merkle_tree_size: int
    inclusion_proof_path: list[str]
    inclusion_leaf_index: int
    checks: VerificationChecks
    verdict: Verdict
    policy_id: str
    policy_version: str


class GetReceiptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str


class GetReceiptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    execution_id: str
    verdict: Verdict
    algorithm: str
    signed_at: datetime
    payload_hash: str
    merkle_root: str | None
    merkle_tree_size: int | None
    policy_id: str
    policy_version: str
    verify_url: str


class ListPoliciesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = Field(
        default=False,
        description="Include policies that are not currently active.",
    )


class PolicyRuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    then: str
    when: dict[str, Any]


class PolicySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    slug: str
    name: str
    description: str | None
    pack: str
    version: int
    is_active: bool
    default_verdict: str
    rules: list[PolicyRuleSummary]


class ListPoliciesOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    policies: list[PolicySummary]
