"""Seal receipts after human approval, rejection, or hold expiration."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.services.governance.receipt import seal_receipt
from axiom.services.governance.verification import VerificationResult


async def seal_pending_after_hold_decision(
    db: AsyncSession,
    *,
    receipt: GovernanceReceipt,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
) -> GovernanceReceipt:
    """Sign and Merkle-seal a pending receipt after verdict + approval rows were updated."""
    vres = VerificationResult(passed=True, mismatches=[], status="skipped")
    return await seal_receipt(
        db,
        receipt=receipt,
        intent=intent,
        verdict=verdict,
        execution_data={},
        executed_at=None,
        verification_result=vres,
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
