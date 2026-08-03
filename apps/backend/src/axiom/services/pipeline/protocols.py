"""Pipeline stage contracts.

Pure interfaces. Must not import routers, middleware, models, or the DB layer.
Import-linter contract ``pipeline-protocols-pure`` enforces this leaf status so
the 6 stages can be composed, tested, and replaced without dragging in a
FastAPI dependency graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from axiom.services.crypto.hybrid_signer import HybridSignature
from axiom.services.policy.evaluator import PolicyDecision
from axiom.services.prompt_injection.detector import InjectionMatch


class PipelineMode(StrEnum):
    """Governance execution mode.

    SHADOW  = observe + record receipt, never block.
    ENFORCE = block on DENY/ESCALATE; allow APPROVE/MODIFY.
    """

    SHADOW = "shadow"
    ENFORCE = "enforce"


@dataclass(frozen=True)
class StageResult:
    """Outcome of a single stage.

    ``ok=False`` causes the runner to short-circuit the decision to DENY and
    route straight through Evidence + Receipt so that every request emits a
    receipt (never silent drops).
    """

    ok: bool
    stage_name: str
    duration_ms: float
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Mutable context threaded through all six stages.

    Stages WRITE to this. The runner reads the final state to compose the
    envelope returned by ``POST /v1/govern``.
    """

    project_id: UUID
    agent_id: UUID
    api_key_id: UUID
    correlation_id: str
    action: dict[str, Any]
    mode: PipelineMode
    requested_at: datetime

    action_canonical: bytes | None = None
    injection_matches: tuple[InjectionMatch, ...] = field(default_factory=tuple)

    policy_id: str | None = None
    policy_version: str | None = None

    decision: PolicyDecision | None = None
    explanation: str | None = None

    dispatched: bool = False

    evidence_plaintext: bytes | None = None
    evidence_nonce: bytes | None = None
    evidence_ciphertext: bytes | None = None
    evidence_key_id: str | None = None
    payload_hash: bytes | None = None

    receipt_id: str | None = None
    execution_id: str | None = None
    signature: HybridSignature | None = None
    merkle_leaf_index: int | None = None
    merkle_leaf_hash: bytes | None = None
    merkle_root: bytes | None = None
    merkle_tree_size: int | None = None
    merkle_audit_path: tuple[bytes, ...] | None = None

    stage_results: list[StageResult] = field(default_factory=list)


@runtime_checkable
class Stage(Protocol):
    """All six stages conform to this Protocol."""

    name: str

    async def execute(self, ctx: PipelineContext) -> StageResult: ...
