"""Governance workflow chains — grouping receipts with chain-level seals."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import (
    GovernanceChain,
    GovernanceIntent,
    GovernanceReceipt,
    GovernanceVerdict,
)
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.receipt.keys import get_signing_keys

logger = structlog.get_logger(__name__)


class ChainValidationError(ValueError):
    """Invalid chain_id or chain state for the request."""


def compute_chain_hash(receipt_hashes_in_order: list[bytes]) -> bytes:
    """SHA-256 over concatenated receipt hashes (32 bytes each), in order."""
    joined = b"".join(receipt_hashes_in_order)
    return hashlib.sha256(joined).digest()


async def create_chain(
    db: AsyncSession,
    project_id: UUID,
    agent_id: str,
    workflow_name: str | None,
) -> GovernanceChain:
    row = GovernanceChain(
        project_id=project_id,
        agent_id=agent_id,
        workflow_name=workflow_name,
        status="active",
    )
    db.add(row)
    await db.flush()
    logger.info(
        "governance.chain.created",
        chain_id=str(row.id),
        project_id=str(project_id),
        agent_id=agent_id,
    )
    return row


async def get_chain(db: AsyncSession, chain_id: UUID) -> GovernanceChain | None:
    return await db.get(GovernanceChain, chain_id)


async def get_or_create_chain(
    db: AsyncSession,
    project_id: UUID,
    agent_id: str,
    workflow_name: str | None,
    chain_id: str | None,
) -> GovernanceChain | None:
    if chain_id is not None and chain_id.strip():
        try:
            cid = UUID(chain_id.strip())
        except ValueError as exc:
            raise ChainValidationError("chain_id must be a valid UUID") from exc
        chain = await get_chain(db, cid)
        if chain is None:
            raise ChainValidationError("chain_id does not exist")
        if chain.project_id != project_id:
            raise ChainValidationError("chain_id does not belong to this project")
        if chain.agent_id != agent_id:
            raise ChainValidationError("chain_id was created by a different agent_id")
        if chain.status != "active":
            raise ChainValidationError("chain is not active")
        return chain

    if workflow_name is not None and workflow_name.strip():
        return await create_chain(db, project_id, agent_id, workflow_name.strip())

    return None


async def update_chain_stats(
    db: AsyncSession,
    chain: GovernanceChain,
    verdict: str | None,
    verification: str | None,
) -> None:
    now = datetime.now(UTC)
    if verdict is not None:
        chain.total_actions += 1
        if verdict == "allow":
            chain.authorized += 1
        elif verdict == "hold":
            chain.held += 1
        elif verdict == "deny":
            chain.denied += 1
        chain.last_activity = now
    if verification is not None:
        if verification == "pass":
            chain.compliant += 1
        elif verification == "fail":
            chain.non_compliant += 1
        chain.last_activity = now
    chain.updated_at = now
    await db.flush()


async def adjust_chain_after_hold_resolution(
    db: AsyncSession,
    chain_id: UUID | None,
    *,
    final_verdict: str,
) -> None:
    """Decrement held (from original govern) and count final allow/deny."""
    if chain_id is None:
        return
    chain = await get_chain(db, chain_id)
    if chain is None:
        return
    now = datetime.now(UTC)
    chain.held = max(0, chain.held - 1)
    if final_verdict == "allow":
        chain.authorized += 1
    elif final_verdict == "deny":
        chain.denied += 1
    chain.updated_at = now
    await db.flush()


async def _receipt_hashes_for_chain(
    db: AsyncSession,
    chain_id: UUID,
) -> list[bytes]:
    """Sealed receipts only, chronological by receipt created_at."""
    stmt = (
        select(GovernanceReceipt.receipt_hash)
        .join(GovernanceIntent, GovernanceReceipt.intent_id == GovernanceIntent.id)
        .where(
            GovernanceIntent.chain_id == chain_id,
            GovernanceReceipt.status == "sealed",
            GovernanceReceipt.receipt_hash.is_not(None),
        )
        .order_by(GovernanceReceipt.created_at)
    )
    rows = await db.scalars(stmt)
    return [bytes(h) for h in rows.all() if h is not None]


async def close_chain(
    db: AsyncSession,
    chain: GovernanceChain,
    *,
    auto_closed: bool = False,
) -> GovernanceChain:
    hashes = await _receipt_hashes_for_chain(db, chain.id)
    chain_digest = compute_chain_hash(hashes)
    keys = get_signing_keys()
    ed_sig = ed25519.sign(keys.ed25519_private, chain_digest)
    ml_sig = ml_dsa.sign(keys.ml_dsa_private, chain_digest)
    now = datetime.now(UTC)
    chain.chain_hash = chain_digest
    chain.ed25519_sig = ed_sig
    chain.ml_dsa_sig = ml_sig
    chain.key_id = keys.ed25519_key_id
    chain.status = "auto_closed" if auto_closed else "sealed"
    chain.closed_at = now
    chain.sealed_at = now
    chain.last_activity = now
    chain.updated_at = now
    await db.flush()
    logger.info(
        "governance.chain.closed",
        chain_id=str(chain.id),
        status=chain.status,
        receipt_count=len(hashes),
    )
    return chain


async def auto_close_stale_chains(
    db: AsyncSession,
    project_id: UUID,
    *,
    timeout_minutes: int = 30,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    stmt = (
        select(GovernanceChain.id)
        .where(
            GovernanceChain.project_id == project_id,
            GovernanceChain.status == "active",
            GovernanceChain.last_activity < cutoff,
        )
        .limit(50)
    )
    ids = list((await db.scalars(stmt)).all())
    closed = 0
    for cid in ids:
        row = await db.get(GovernanceChain, cid)
        if row is None or row.status != "active":
            continue
        await close_chain(db, row, auto_closed=True)
        closed += 1
    if closed:
        await db.flush()
    return closed


async def list_chains(
    db: AsyncSession,
    project_id: UUID,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
) -> tuple[list[GovernanceChain], int]:
    conditions = [GovernanceChain.project_id == project_id]
    if status is not None:
        conditions.append(GovernanceChain.status == status)
    count_stmt = select(func.count()).select_from(GovernanceChain).where(*conditions)
    total = int(await db.scalar(count_stmt) or 0)
    offset = max(page - 1, 0) * per_page
    stmt = (
        select(GovernanceChain)
        .where(*conditions)
        .order_by(GovernanceChain.started_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = await db.scalars(stmt)
    return list(rows.all()), total


async def list_receipt_summaries_for_chain(
    db: AsyncSession,
    chain_id: UUID,
) -> list[dict]:
    stmt = (
        select(GovernanceReceipt, GovernanceIntent, GovernanceVerdict)
        .join(GovernanceIntent, GovernanceReceipt.intent_id == GovernanceIntent.id)
        .join(GovernanceVerdict, GovernanceReceipt.verdict_id == GovernanceVerdict.id)
        .where(GovernanceIntent.chain_id == chain_id)
        .order_by(GovernanceReceipt.created_at)
    )
    result = await db.execute(stmt)
    records: list[dict] = []
    for receipt, _intent, verdict in result.all():
        records.append(
            {
                "receipt_id": str(receipt.id),
                "intent_id": str(receipt.intent_id),
                "verdict_id": str(verdict.id),
                "status": receipt.status,
                "verdict": verdict.verdict,
                "sealed_at": receipt.sealed_at.isoformat() if receipt.sealed_at else None,
                "receipt_hash": receipt.receipt_hash.hex() if receipt.receipt_hash else None,
                "created_at": receipt.created_at.isoformat(),
            }
        )
    return records


async def get_chain_with_records(
    db: AsyncSession,
    chain_id: UUID,
) -> tuple[GovernanceChain, list[dict]]:
    chain = await get_chain(db, chain_id)
    if chain is None:
        msg = "Chain not found"
        raise ValueError(msg)
    records = await list_receipt_summaries_for_chain(db, chain_id)
    return chain, records


def verify_chain_signatures(chain: GovernanceChain) -> dict[str, bool] | None:
    if chain.chain_hash is None or chain.ed25519_sig is None:
        return None
    keys = get_signing_keys()
    ed_ok = ed25519.verify(keys.ed25519_public, chain.chain_hash, chain.ed25519_sig)
    ml_ok = False
    if chain.ml_dsa_sig:
        ml_ok = ml_dsa.verify(keys.ml_dsa_public, chain.chain_hash, chain.ml_dsa_sig)
    return {"ed25519": ed_ok, "ml_dsa_65": ml_ok}


def chain_compliance_rate(chain: GovernanceChain) -> float:
    if chain.total_actions == 0:
        return 0.0
    return 100.0 * float(chain.compliant) / float(chain.total_actions)
