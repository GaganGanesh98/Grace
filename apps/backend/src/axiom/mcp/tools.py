"""The five MCP governance tools.

Design constraint worth restating: these handlers *orchestrate*, they do not
*decide*. `govern_action` calls the same ``ReceiptService.process`` that
``POST /v1/govern`` calls; `verify_receipt` performs the same four checks as
``GET /v1/verify/{id}``. If a change here would alter a verdict or a
signature, it belongs in ``axiom.services``, not in this file.

A note on prose
---------------
Every output model leads with a natural-language field (``decision`` /
``summary``). This is not decoration. The consumer is a language model, and a
model skimming a JSON blob will readily miss ``{"verdict": "deny"}`` buried
among fifteen other keys and proceed anyway. Stating the outcome in a
sentence, first, is the difference between a governance tool that governs and
one that merely records.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.mcp import schemas
from axiom.mcp.auth import (
    SCOPE_READ,
    SCOPE_WRITE,
    MCPPrincipal,
    reverify_for_write,
)
from axiom.models.execution import Execution
from axiom.models.policy import Policy as PolicyModel
from axiom.models.receipt import Receipt
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.crypto.merkle import (
    InclusionProof,
    build_tree,
    inclusion_proof,
    verify_inclusion,
)
from axiom.services.pipeline.protocols import PipelineMode
from axiom.services.policy.evaluator import Policy, Verdict, evaluate
from axiom.services.receipt.keys import get_signing_keys
from axiom.services.receipt.merkle_append import MerkleAppender
from axiom.services.receipt.service import ReceiptService

logger = structlog.get_logger(__name__)

_MAX_ACTION_BYTES = 100 * 1024


class ToolError(Exception):
    """A tool-level failure surfaced to the MCP client as an error."""


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _verify_url(receipt_id: str) -> str:
    settings = get_settings()
    return f"{settings.verify_base_url.rstrip('/')}/v1/verify/{receipt_id}"


def _assert_action_size(action: dict[str, Any]) -> None:
    """Mirror the 100 KB cap enforced on ``POST /v1/govern``.

    Enforced on the canonical encoding rather than a Content-Length header,
    since MCP has no equivalent header to trust.
    """

    try:
        encoded = canonicalize(action)
    except (TypeError, ValueError) as exc:
        raise ToolError(f"Action is not JSON-serialisable: {exc}") from exc
    if len(encoded) > _MAX_ACTION_BYTES:
        raise ToolError(
            f"Action exceeds the 100 KB cap ({len(encoded)} bytes). "
            "Summarise or externalise large payloads before submitting."
        )


def _payload_hash_matches(receipt: Receipt) -> bool:
    """Recompute the evidence envelope hash and compare it to the stored one.

    Stage 5 (Evidence) defines ``payload_hash`` as::

        sha256(nonce || ciphertext || key_id.encode("utf-8"))

    — see ``axiom.services.pipeline.stages.evidence``. Recomputing it here is a
    real check: it proves the stored evidence envelope is byte-for-byte the one
    whose hash was signed and anchored in the Merkle tree, so tampering with
    the ciphertext after the fact is detectable without decrypting anything.

    Fails closed when any component is absent — an unverifiable receipt is not
    a verified one.
    """

    if receipt.evidence_nonce is None or receipt.evidence_ciphertext is None:
        return False
    if not receipt.evidence_key_id:
        return False
    hasher = hashlib.sha256()
    hasher.update(receipt.evidence_nonce)
    hasher.update(receipt.evidence_ciphertext)
    hasher.update(receipt.evidence_key_id.encode("utf-8"))
    return hasher.digest() == receipt.payload_hash


def _decision_sentence(
    verdict: Verdict,
    reasoning: str,
    *,
    modification: dict[str, Any] | None,
    escalation_target: str | None,
    shadow: bool,
) -> str:
    """Render the verdict as an unambiguous instruction to the calling agent."""

    if shadow:
        prefix = (
            "SHADOW MODE — this action was recorded but NOT blocked, whatever the "
            "verdict below. Proceed as your own logic dictates. Verdict: "
        )
    else:
        prefix = ""

    if verdict is Verdict.APPROVE:
        body = f"ALLOWED. You may proceed with this action as submitted. {reasoning}"
    elif verdict is Verdict.DENY:
        body = (
            f"DENIED. You must NOT perform this action. Do not retry it and do not "
            f"attempt a variation intended to evade this decision. {reasoning}"
        )
    elif verdict is Verdict.MODIFY:
        body = (
            f"MODIFIED. You must NOT use your original action. Use the 'modification' "
            f"field instead, exactly as given. {reasoning}"
        )
        if modification is None:
            body += (
                " WARNING: the policy returned 'modify' without supplying a "
                "modification. Treat this as a denial and stop."
            )
    elif verdict is Verdict.ESCALATE:
        target = escalation_target or "a human reviewer"
        body = (
            f"ESCALATED. You must NOT proceed. This action requires approval from "
            f"{target}. Stop and report that approval is pending. {reasoning}"
        )
    else:  # pragma: no cover - StrEnum is exhaustive
        body = f"UNKNOWN VERDICT ({verdict}). Treat as a denial and stop. {reasoning}"

    return prefix + body


async def govern_action(
    db: AsyncSession,
    principal: MCPPrincipal,
    payload: schemas.GovernActionInput,
) -> schemas.GovernActionOutput:
    """Govern an action end-to-end and seal a signed receipt.

    Scope: ``mcp:write``.
    """

    principal.require_scope(SCOPE_WRITE)
    await reverify_for_write(db, principal)
    _assert_action_size(payload.action)

    correlation_id = str(uuid.uuid4())
    service = ReceiptService(db)
    ctx = await service.process(
        project_id=principal.ctx.project_id,
        agent_id=payload.agent_id,
        api_key_id=principal.ctx.api_key_id,
        correlation_id=correlation_id,
        action=payload.action,
        mode=payload.mode,
    )

    if (
        ctx.receipt_id is None
        or ctx.signature is None
        or ctx.merkle_root is None
        or ctx.merkle_tree_size is None
        or ctx.merkle_leaf_index is None
        or ctx.execution_id is None
        or ctx.decision is None
    ):
        logger.error(
            "mcp.govern.receipt_incomplete",
            correlation_id=correlation_id,
            project_id=str(principal.ctx.project_id),
        )
        raise ToolError(
            "Governance pipeline did not produce a complete receipt. The action was "
            "not authorised; do not proceed."
        )

    decision = ctx.decision
    shadow = payload.mode is PipelineMode.SHADOW

    return schemas.GovernActionOutput(
        decision=_decision_sentence(
            decision.verdict,
            decision.reasoning,
            modification=decision.modification,
            escalation_target=decision.escalation_target,
            shadow=shadow,
        ),
        verdict=decision.verdict,
        allowed=decision.verdict is Verdict.APPROVE,
        reasoning=decision.reasoning,
        explanation=ctx.explanation or "",
        modification=decision.modification,
        escalation_target=decision.escalation_target,
        receipt_id=ctx.receipt_id,
        execution_id=ctx.execution_id,
        verify_url=_verify_url(ctx.receipt_id),
        merkle_leaf_index=ctx.merkle_leaf_index,
        merkle_tree_size=ctx.merkle_tree_size,
        merkle_root=_b64(ctx.merkle_root),
        algorithm=ctx.signature.algorithm,
        signed_at=ctx.requested_at,
        dispatched=ctx.dispatched,
        correlation_id=correlation_id,
    )


def _coerce_policy(row: PolicyModel) -> Policy:
    """Coerce a DB policy row into the evaluator's model.

    Mirrors ``axiom.services.pipeline.stages.authority._coerce_policy``. Kept
    in step with it deliberately: if that coercion changes, this must too, or
    check_policy will predict a verdict the real pipeline would not reach.
    """

    raw_rules = row.rules if isinstance(row.rules, list) else []
    clean: list[dict[str, Any]] = []
    for raw in raw_rules:
        if not isinstance(raw, dict):
            continue
        clean.append(
            {
                "id": str(raw.get("id", "")),
                "description": str(raw.get("description", "")),
                "when": raw.get("when", {}) if isinstance(raw.get("when"), dict) else {},
                "then": raw.get("then", "deny"),
                "modification": raw.get("modification"),
                "escalation_target": raw.get("escalation_target"),
            }
        )
    return Policy.model_validate(
        {
            "id": str(row.id),
            "name": row.name,
            "version": str(row.version),
            "rules": clean,
            "default_verdict": "deny",
        }
    )


async def _load_policy_row(
    db: AsyncSession,
    project_id: UUID,
    policy_id: UUID | None,
) -> PolicyModel | None:
    stmt = select(PolicyModel).where(
        PolicyModel.project_id == project_id,
        PolicyModel.deleted_at.is_(None),
    )
    if policy_id is not None:
        stmt = stmt.where(PolicyModel.id == policy_id)
    else:
        stmt = stmt.where(PolicyModel.is_active.is_(True))
    stmt = stmt.order_by(PolicyModel.version.desc()).limit(1)
    row: PolicyModel | None = await db.scalar(stmt)
    return row


async def check_policy(
    db: AsyncSession,
    principal: MCPPrincipal,
    payload: schemas.CheckPolicyInput,
) -> schemas.CheckPolicyOutput:
    """Dry-run a policy evaluation. Creates no receipt.

    Scope: ``mcp:read``.
    """

    principal.require_scope(SCOPE_READ)
    _assert_action_size(payload.action)

    row = await _load_policy_row(db, principal.ctx.project_id, payload.policy_id)
    if row is None:
        # Match the pipeline's fail-closed posture: absence of policy is a
        # denial, never a pass-through.
        return schemas.CheckPolicyOutput(
            decision=(
                "WOULD BE DENIED. No applicable policy is configured for this project, "
                "and Grace fails closed. This is a dry run — no receipt was created."
            ),
            verdict=Verdict.DENY,
            allowed=False,
            reasoning="no policy configured",
            rule_id=None,
            policy_id="",
            policy_version="",
        )

    policy = _coerce_policy(row)
    decision = evaluate(policy, payload.action)

    sentence = _decision_sentence(
        decision.verdict,
        decision.reasoning,
        modification=decision.modification,
        escalation_target=decision.escalation_target,
        shadow=False,
    )
    return schemas.CheckPolicyOutput(
        decision=(
            f"DRY RUN (no receipt created, not an audit record). "
            f"If submitted to govern_action this would be: {sentence}"
        ),
        verdict=decision.verdict,
        allowed=decision.verdict is Verdict.APPROVE,
        reasoning=decision.reasoning,
        rule_id=decision.rule_id,
        policy_id=decision.policy_id,
        policy_version=decision.policy_version,
        modification=decision.modification,
        escalation_target=decision.escalation_target,
    )


async def _load_scoped_receipt(
    db: AsyncSession,
    project_id: UUID,
    receipt_id: str,
) -> tuple[Receipt, Execution]:
    """Load a receipt and its execution, enforcing project tenancy.

    Returns "not found" for a receipt belonging to another project rather
    than "forbidden" — matching Grace's enumeration-resistance posture
    elsewhere (see the 404-not-403 handling in the project routers). A caller
    must not be able to confirm a receipt id exists in a tenant they cannot read.
    """

    receipt = await db.get(Receipt, receipt_id)
    if receipt is None:
        raise ToolError(f"Receipt {receipt_id} not found.")
    execution = await db.scalar(select(Execution).where(Execution.id == receipt.execution_id))
    if execution is None:
        logger.warning("mcp.receipt.orphan", receipt_id=receipt_id)
        raise ToolError(f"Receipt {receipt_id} not found.")
    if execution.project_id != project_id:
        raise ToolError(f"Receipt {receipt_id} not found.")
    return receipt, execution


async def verify_receipt(
    db: AsyncSession,
    principal: MCPPrincipal,
    payload: schemas.VerifyReceiptInput,
) -> schemas.VerifyReceiptOutput:
    """Verify a receipt's signatures and Merkle inclusion.

    Scope: ``mcp:read``. Runs the same four checks as ``GET /v1/verify/{id}``.
    """

    principal.require_scope(SCOPE_READ)
    receipt, execution = await _load_scoped_receipt(
        db, principal.ctx.project_id, payload.receipt_id
    )

    merkle_root = receipt.merkle_root
    merkle_tree_size = receipt.merkle_tree_size
    if merkle_root is None or merkle_tree_size is None:
        raise ToolError(f"Receipt {payload.receipt_id} is unsigned or incomplete.")

    appender = MerkleAppender()
    historical = await appender.rebuild_tree(
        db,
        project_id=execution.project_id,
        up_to_size=merkle_tree_size,
    )
    leaf_index: int | None = None
    for i, payload_hash in enumerate(historical):
        if payload_hash == receipt.payload_hash:
            leaf_index = i
            break

    if leaf_index is None or len(historical) != merkle_tree_size:
        logger.warning("mcp.verify.merkle_state_mismatch", receipt_id=payload.receipt_id)
        merkle_valid = False
        audit_path: tuple[bytes, ...] = ()
    else:
        tree = build_tree(historical)
        proof = inclusion_proof(tree, leaf_index)
        audit_path = proof.path
        merkle_valid = verify_inclusion(
            merkle_root,
            receipt.payload_hash,
            InclusionProof(
                leaf_index=leaf_index,
                tree_size=merkle_tree_size,
                path=audit_path,
            ),
        )

    keys = get_signing_keys()
    signed_body = {
        "algorithm": receipt.algorithm,
        "receipt_id": receipt.id,
        "payload_hash": _b64(receipt.payload_hash),
        "evidence_key_id": receipt.evidence_key_id or "",
        "merkle": {
            "leaf_index": leaf_index if leaf_index is not None else -1,
            "tree_size": merkle_tree_size,
            "root": _b64(merkle_root),
        },
    }
    canonical_bytes = canonicalize(signed_body)
    payload_hash_matches = _payload_hash_matches(receipt)

    ed_valid = receipt.ed25519_key_id == keys.ed25519_key_id and ed25519.verify(
        keys.ed25519_public, canonical_bytes, receipt.ed25519_signature
    )
    ml_valid = receipt.ml_dsa_key_id == keys.ml_dsa_key_id and ml_dsa.verify(
        keys.ml_dsa_public, canonical_bytes, receipt.ml_dsa_signature
    )

    verified = bool(ed_valid and ml_valid and merkle_valid and payload_hash_matches)

    if verified:
        summary = (
            f"VERIFIED. Receipt {receipt.id} is authentic: both signatures "
            f"(Ed25519 and ML-DSA-65) are valid and the receipt is provably included "
            f"in the audit log at leaf {leaf_index} of {merkle_tree_size}."
        )
    else:
        failed = [
            name
            for name, ok in (
                ("Ed25519 signature", ed_valid),
                ("ML-DSA-65 signature", ml_valid),
                ("Merkle inclusion", merkle_valid),
                ("payload hash", payload_hash_matches),
            )
            if not ok
        ]
        summary = (
            f"NOT VERIFIED. Receipt {receipt.id} failed these checks: "
            f"{', '.join(failed)}. Do not treat this receipt as evidence."
        )

    return schemas.VerifyReceiptOutput(
        summary=summary,
        receipt_id=receipt.id,
        verified=verified,
        algorithm=receipt.algorithm,
        signed_at=receipt.created_at,
        payload_hash=_b64(receipt.payload_hash),
        merkle_root=_b64(merkle_root),
        merkle_tree_size=merkle_tree_size,
        inclusion_proof_path=[_b64(p) for p in audit_path],
        inclusion_leaf_index=leaf_index if leaf_index is not None else -1,
        checks=schemas.VerificationChecks(
            ed25519_signature_valid=ed_valid,
            ml_dsa_signature_valid=ml_valid,
            merkle_inclusion_valid=merkle_valid,
            payload_hash_matches=payload_hash_matches,
        ),
        verdict=Verdict(execution.verdict),
        policy_id=execution.policy_id,
        policy_version=execution.policy_version,
    )


async def get_receipt(
    db: AsyncSession,
    principal: MCPPrincipal,
    payload: schemas.GetReceiptInput,
) -> schemas.GetReceiptOutput:
    """Fetch a single receipt's metadata within the caller's project.

    Scope: ``mcp:read``. Never returns evidence ciphertext or nonce.
    """

    principal.require_scope(SCOPE_READ)
    receipt, execution = await _load_scoped_receipt(
        db, principal.ctx.project_id, payload.receipt_id
    )

    return schemas.GetReceiptOutput(
        receipt_id=receipt.id,
        execution_id=receipt.execution_id,
        verdict=Verdict(execution.verdict),
        algorithm=receipt.algorithm,
        signed_at=receipt.created_at,
        payload_hash=_b64(receipt.payload_hash),
        merkle_root=_b64(receipt.merkle_root) if receipt.merkle_root else None,
        merkle_tree_size=receipt.merkle_tree_size,
        policy_id=execution.policy_id,
        policy_version=execution.policy_version,
        verify_url=_verify_url(receipt.id),
    )


async def list_policies(
    db: AsyncSession,
    principal: MCPPrincipal,
    payload: schemas.ListPoliciesInput,
) -> schemas.ListPoliciesOutput:
    """List the project's policies and their rules.

    Scope: ``mcp:read``. An agent that can read the rules can comply with
    them deliberately instead of discovering them through denials.
    """

    principal.require_scope(SCOPE_READ)

    stmt = select(PolicyModel).where(
        PolicyModel.project_id == principal.ctx.project_id,
        PolicyModel.deleted_at.is_(None),
    )
    if not payload.include_inactive:
        stmt = stmt.where(PolicyModel.is_active.is_(True))
    stmt = stmt.order_by(PolicyModel.slug, PolicyModel.version.desc())
    rows = list(await db.scalars(stmt))

    summaries: list[schemas.PolicySummary] = []
    for row in rows:
        raw_rules = row.rules if isinstance(row.rules, list) else []
        rule_summaries: list[schemas.PolicyRuleSummary] = []
        for raw in raw_rules:
            if not isinstance(raw, dict):
                continue
            # Skip metadata-only entries such as {"block_on_injection": true}.
            if "id" not in raw and "when" not in raw:
                continue
            rule_summaries.append(
                schemas.PolicyRuleSummary(
                    id=str(raw.get("id", "")),
                    description=str(raw.get("description", "")),
                    then=str(raw.get("then", "deny")),
                    when=raw.get("when", {}) if isinstance(raw.get("when"), dict) else {},
                )
            )
        summaries.append(
            schemas.PolicySummary(
                policy_id=str(row.id),
                slug=row.slug,
                name=row.name,
                description=row.description,
                pack=row.pack,
                version=row.version,
                is_active=row.is_active,
                default_verdict="deny",
                rules=rule_summaries,
            )
        )

    if not summaries:
        summary = (
            "No policies are configured for this project. Grace fails closed: with no "
            "policy, every governed action is denied."
        )
    else:
        summary = (
            f"{len(summaries)} polic{'y' if len(summaries) == 1 else 'ies'} in scope. "
            "Rules are evaluated in order, first match wins; if no rule matches, the "
            "default verdict is DENY."
        )

    return schemas.ListPoliciesOutput(summary=summary, policies=summaries)
