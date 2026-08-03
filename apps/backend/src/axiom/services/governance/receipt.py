"""Stage 5-7: pending receipt, execution, sealing."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.crypto.merkle import build_tree, inclusion_proof
from axiom.services.governance.verification import VerificationResult
from axiom.services.receipt.keys import get_signing_keys

logger = structlog.get_logger(__name__)

_project_leaves: dict[UUID, list[bytes]] = {}
_project_locks: dict[UUID, asyncio.Lock] = {}


def _lock_for(project_id: UUID) -> asyncio.Lock:
    if project_id not in _project_locks:
        _project_locks[project_id] = asyncio.Lock()
    return _project_locks[project_id]


def reset_governance_merkle_for_tests() -> None:
    _project_leaves.clear()
    _project_locks.clear()


async def load_governance_merkle_from_db(db: AsyncSession) -> None:
    """Startup: rebuild in-memory leaf sequences from sealed rows."""
    rows = await db.scalars(
        select(GovernanceReceipt)
        .where(
            GovernanceReceipt.status == "sealed",
            GovernanceReceipt.receipt_hash.is_not(None),
        )
        .order_by(GovernanceReceipt.project_id, GovernanceReceipt.created_at)
    )
    _project_leaves.clear()
    for row in rows:
        if row.receipt_hash:
            digest = bytes(row.receipt_hash)
            lst = _project_leaves.setdefault(row.project_id, [])
            lst.append(digest)


async def _load_project_leaves_from_db(db: AsyncSession, project_id: UUID) -> list[bytes]:
    rows = await db.scalars(
        select(GovernanceReceipt.receipt_hash)
        .where(
            GovernanceReceipt.project_id == project_id,
            GovernanceReceipt.status == "sealed",
            GovernanceReceipt.receipt_hash.is_not(None),
        )
        .order_by(GovernanceReceipt.created_at)
    )
    return [bytes(h) for h in rows if h is not None]


async def persist_merkle_state_snapshot(db: AsyncSession) -> None:
    _ = db
    logger.info(
        "governance.merkle.persist_skipped",
        note="MVP: sealed rows already store receipt_hash; in-memory cache is rebuildable",
    )


def _intent_snapshot(intent: GovernanceIntent) -> dict[str, Any]:
    return {
        "id": str(intent.id),
        "agent_id": intent.agent_id,
        "action_type": intent.action_type,
        "target": intent.target,
        "parameters": intent.parameters,
        "risk_declared": intent.risk_declared,
        "mode": intent.mode,
        "metadata": intent.extra_metadata,
    }


def _verdict_snapshot(verdict: GovernanceVerdict) -> dict[str, Any]:
    return {
        "id": str(verdict.id),
        "verdict": verdict.verdict,
        "reason": verdict.reason,
        "policy_version": verdict.policy_version,
        "rules_evaluated": verdict.rules_evaluated,
        "risk_assessed": verdict.risk_assessed,
        "context": verdict.context,
    }


def approval_dict_from_receipt(receipt: GovernanceReceipt) -> dict[str, Any] | None:
    """Include in the signed canonical payload when a hold was resolved (not pending)."""
    st = receipt.approval_status
    if st is None or st == "pending":
        return None
    return {
        "status": st,
        "approved_by_user_id": str(receipt.approved_by_user_id)
        if receipt.approved_by_user_id
        else None,
        "approved_at": receipt.approved_at.isoformat() if receipt.approved_at else None,
        "reason": receipt.approval_reason,
        "expires_at": receipt.approval_expires_at.isoformat()
        if receipt.approval_expires_at
        else None,
    }


async def create_pending_receipt(
    db: AsyncSession,
    *,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
) -> GovernanceReceipt:
    row = GovernanceReceipt(
        intent_id=intent.id,
        verdict_id=verdict.id,
        project_id=intent.project_id,
        status="pending",
        verification="pending",
        mismatches=[],
    )
    db.add(row)
    await db.flush()
    return row


def unsigned_receipt_for_sealing(
    *,
    receipt_id: str,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
    execution_data: dict[str, Any] | None,
    verification_status: str,
    mismatches: list[dict[str, Any]],
    executed_at: datetime | None,
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "v": 1,
        "receipt_id": receipt_id,
        "project_id": str(intent.project_id),
        "intent_id": str(intent.id),
        "verdict_id": str(verdict.id),
        "policy_version": verdict.policy_version,
        "intent": _intent_snapshot(intent),
        "verdict": _verdict_snapshot(verdict),
        "execution": execution_data or {},
        "executed_at": executed_at.isoformat() if executed_at else None,
        "verification": {
            "status": verification_status,
            "mismatches": mismatches,
        },
    }
    if approval is not None:
        out["approval"] = approval
    return out


async def seal_receipt(
    db: AsyncSession,
    *,
    receipt: GovernanceReceipt,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
    execution_data: dict[str, Any] | None,
    executed_at: datetime | None,
    verification_result: VerificationResult,
) -> GovernanceReceipt:
    keys = get_signing_keys()
    verification_status = verification_result.status
    mismatches = list(verification_result.mismatches)

    payload = unsigned_receipt_for_sealing(
        receipt_id=str(receipt.id),
        intent=intent,
        verdict=verdict,
        execution_data=execution_data,
        verification_status=verification_status,
        mismatches=mismatches,
        executed_at=executed_at,
        approval=approval_dict_from_receipt(receipt),
    )

    try:
        canonical = canonicalize(payload)
    except (TypeError, ValueError):
        logger.exception("governance.seal.canonicalize_failed", receipt_id=str(receipt.id))
        receipt.status = "failed"
        receipt.updated_at = datetime.now(UTC)
        await db.flush()
        msg = "Canonical JSON serialization failed"
        raise RuntimeError(msg) from None

    receipt_hash = hashlib.sha256(canonical).digest()

    try:
        ed_sig = ed25519.sign(keys.ed25519_private, canonical)
        ml_sig = ml_dsa.sign(keys.ml_dsa_private, canonical)
    except Exception:  # noqa: BLE001
        logger.exception("governance.seal.sign_failed", receipt_id=str(receipt.id))
        receipt.status = "failed"
        receipt.updated_at = datetime.now(UTC)
        await db.flush()
        raise

    leaf_preimage = receipt_hash
    async with _lock_for(intent.project_id):
        leaves = _project_leaves.get(intent.project_id)
        if leaves is None:
            leaves = await _load_project_leaves_from_db(db, intent.project_id)
        new_leaves = [*leaves, leaf_preimage]
        tree = build_tree(tuple(new_leaves))
        proof = inclusion_proof(tree, len(new_leaves) - 1)
        _project_leaves[intent.project_id] = list(new_leaves)

    proof_payload = {
        "leaf_index": proof.leaf_index,
        "tree_size": proof.tree_size,
        "path": [h.hex() for h in proof.path],
    }

    receipt.execution_data = execution_data
    receipt.executed_at = executed_at
    receipt.verification = verification_status
    receipt.mismatches = mismatches
    receipt.receipt_hash = receipt_hash
    receipt.ed25519_sig = ed_sig
    receipt.ml_dsa_sig = ml_sig
    receipt.merkle_leaf = leaf_preimage
    receipt.merkle_root = tree.root
    receipt.merkle_proof = proof_payload
    receipt.key_id = keys.ed25519_key_id
    receipt.status = "sealed"
    receipt.sealed_at = datetime.now(UTC)
    receipt.updated_at = datetime.now(UTC)
    await db.flush()
    return receipt
