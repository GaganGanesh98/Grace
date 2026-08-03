"""Pydantic schemas for /v1/govern, /v1/verify, /v1/disclose.

All request models are strict (``extra="forbid"``). Response models are
also strict so accidental leaks land as 500s in CI rather than shipping
to the internet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axiom.services.pipeline.protocols import PipelineMode
from axiom.services.policy.evaluator import Verdict


class GovernanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: dict[str, Any] = Field(...)
    agent_id: UUID
    mode: PipelineMode = PipelineMode.ENFORCE


class GovernanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    execution_id: str
    verdict: Verdict
    reasoning: str
    explanation: str
    modification: dict[str, Any] | None = None
    escalation_target: str | None = None
    merkle_leaf_index: int
    merkle_tree_size: int
    merkle_root: str
    verify_url: str
    dispatched: bool
    correlation_id: str
    algorithm: str
    signed_at: datetime


class InclusionProofSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leaf_index: int
    tree_size: int
    path: list[str]  # base64-encoded sibling hashes, leaf-to-root order


class VerificationDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ed25519_signature_valid: bool
    ml_dsa_signature_valid: bool
    merkle_inclusion_valid: bool
    payload_hash_matches: bool


class VerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    verified: bool
    algorithm: str
    signed_at: datetime
    payload_hash: str
    merkle_root: str
    merkle_tree_size: int
    inclusion_proof: InclusionProofSchema
    verification_details: VerificationDetails
    project_id: UUID
    policy_id: str
    policy_version: str
    verdict: Verdict
    ed25519_key_id: str
    ml_dsa_key_id: str
    ed25519_public_pem: str
    ml_dsa_public_b64: str


class DiscloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_date: datetime
    to_date: datetime
    agent_id: UUID | None = None
    action_type: str | None = None
    page: int = Field(1, ge=1)
    per_page: int = Field(100, ge=1, le=100)


class DisclosedReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    execution_id: str
    created_at: datetime
    verdict: Verdict
    policy_id: str
    policy_version: str
    reasoning: str
    explanation: str | None
    correlation_id: str
    inclusion_proof: InclusionProofSchema
    merkle_root: str
    merkle_tree_size: int
    evidence: dict[str, Any]


class DiscloseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    page: int
    per_page: int
    receipts: list[DisclosedReceipt]


# --- Phase 2.5 governance engine (separate from legacy /v1/govern) ---


class GovernRequest(BaseModel):
    """Agent submits intent for governance evaluation."""

    agent_id: str = Field(..., min_length=1, max_length=255)
    action_type: str = Field(..., min_length=1, max_length=255)
    target: str = Field(..., min_length=1, max_length=1024)
    parameters: dict = Field(default_factory=dict)
    risk: str = Field(..., pattern="^(low|medium|high|critical)$")
    mode: str = Field(default="enforce", pattern="^(enforce|shadow|dry_run)$")
    metadata: dict = Field(default_factory=dict)
    workflow: str | None = Field(
        None,
        max_length=255,
        description="Workflow name — auto-creates a chain if no chain_id provided",
    )
    chain_id: str | None = Field(None, description="Existing chain ID to add this action to")

    model_config = ConfigDict(extra="forbid")


class ReportRequest(BaseModel):
    """Agent reports what actually happened after execution."""

    receipt_id: str = Field(..., description="Receipt ID from govern response")
    outcome: dict = Field(..., description="What actually happened")
    executed_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class VerifyGovernanceByReceiptIdRequest(BaseModel):
    """Server-side verify: load a sealed governance receipt from the database."""

    receipt_id: str = Field(..., min_length=1, description="Governance receipt UUID from govern/report")

    model_config = ConfigDict(extra="forbid")


class VerifyReceiptRequest(BaseModel):
    """Anyone submits a receipt for independent verification."""

    receipt_json: str = Field(..., description="The full receipt as JSON string")
    ed25519_signature: str = Field(..., description="Base64-encoded Ed25519 signature")
    ml_dsa_signature: str | None = Field(None, description="Base64-encoded ML-DSA signature")
    merkle_proof: list[str] = Field(default_factory=list, description="Hex-encoded proof hashes")
    merkle_root: str = Field(..., description="Hex-encoded expected root")
    ed25519_public_key: str = Field(..., description="Base64-encoded public key")
    ml_dsa_public_key: str | None = None
    leaf_index: int | None = None
    tree_size: int | None = None
    leaf_preimage_hex: str | None = Field(
        None,
        description="Hex-encoded 32-byte leaf preimage (receipt hash digest) for Merkle verify",
    )

    model_config = ConfigDict(extra="forbid")


class GovernResponse(BaseModel):
    """Returned from POST /v1/governance/govern."""

    receipt_id: str
    verdict: str
    reason: str | None
    policy_version: str
    risk_assessed: str
    mode: str
    chain_id: str | None = None
    approval_status: Literal["pending", "approved", "rejected", "expired"] | None = None
    approval_expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class ReportResponse(BaseModel):
    """Returned from POST /v1/governance/report."""

    receipt_id: str
    status: str
    verification: str
    mismatches: list[dict]
    signatures: dict
    merkle: dict

    model_config = ConfigDict(extra="forbid")


class EngineReceiptResponse(BaseModel):
    """Full receipt returned from GET /v1/governance/receipts/{id}."""

    id: str
    intent: dict
    verdict: dict
    execution: dict | None
    verification: dict
    signatures: dict
    merkle: dict
    policy_version: str
    sealed_at: datetime | None
    status: str
    signer_public: dict | None = None
    approval_status: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    approval_reason: str | None = None
    approval_expires_at: datetime | None = None
    duration_ms: int | None = None
    """(sealed_at - created_at) in ms when sealed; computed at serialize, not stored."""

    model_config = ConfigDict(extra="forbid")


class ApprovalRequest(BaseModel):
    """Body for POST .../approve and .../reject."""

    reason: str | None = Field(None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class ApprovalResponse(BaseModel):
    receipt_id: UUID
    approval_status: Literal["approved", "rejected"]
    approved_by: str
    approved_at: datetime
    verdict: Literal["allow", "deny"]
    reason: str | None

    model_config = ConfigDict(extra="forbid")


class ExtendHoldResponse(BaseModel):
    approval_expires_at: datetime

    model_config = ConfigDict(extra="forbid")


class PendingReceiptSummary(BaseModel):
    receipt_id: UUID
    agent_id: str
    action_type: str
    target: str
    risk: str
    reason: str | None
    created_at: datetime
    approval_expires_at: datetime
    time_remaining_seconds: int

    model_config = ConfigDict(extra="forbid")


class PendingReceiptsResponse(BaseModel):
    receipts: list[PendingReceiptSummary]
    total: int

    model_config = ConfigDict(extra="forbid")


class GovernanceEngineVerifyResponse(BaseModel):
    """Returned from POST /v1/governance/verify (independent checks)."""

    valid: bool
    checks: dict
    errors: list[str]

    model_config = ConfigDict(extra="forbid")


class ChainCloseRequest(BaseModel):
    """Close and seal a governance chain."""

    model_config = ConfigDict(extra="forbid")


class ChainSummary(BaseModel):
    """Chain summary returned from GET /v1/chains/{id}."""

    id: str
    workflow_name: str | None
    agent_id: str
    status: str
    total_actions: int
    authorized: int
    held: int
    denied: int
    compliant: int
    non_compliant: int
    compliance_rate: float
    chain_signature: dict | None
    started_at: datetime
    closed_at: datetime | None
    sealed_at: datetime | None
    records: list[dict]

    model_config = ConfigDict(extra="forbid")


class ChainListResponse(BaseModel):
    """List of chains returned from GET /v1/chains."""

    chains: list[ChainSummary]
    total: int
    page: int
    per_page: int

    model_config = ConfigDict(extra="forbid")


class ActiveGovernancePolicyResponse(BaseModel):
    """Active YAML governance policy for a project (from ``project.settings``)."""

    name: str
    display_name: str
    version: str
    rules: list[dict[str, Any]]
    is_default_configuration: bool

    model_config = ConfigDict(extra="forbid")
