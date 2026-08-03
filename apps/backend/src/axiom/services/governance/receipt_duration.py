"""Serialization-time helpers for governance receipt API (Phase 7.5.4)."""

from __future__ import annotations

import structlog

from axiom.models.governance import GovernanceReceipt

logger = structlog.get_logger(__name__)

_MAX_PLAUSIBLE_MS = 3_600_000  # 1 hour; beyond this is clock skew or corruption


def compute_receipt_duration_ms(receipt: GovernanceReceipt) -> int | None:
    """(sealed_at - created_at) in ms, or None when not meaningful."""
    if receipt.status != "sealed" or receipt.sealed_at is None:
        return None
    delta = receipt.sealed_at - receipt.created_at
    ms = int(round(delta.total_seconds() * 1000))
    if ms < 0 or ms > _MAX_PLAUSIBLE_MS:
        logger.warning(
            "governance.receipt.duration_ms_clamped",
            receipt_id=str(receipt.id),
            created_at=receipt.created_at.isoformat(),
            sealed_at=receipt.sealed_at.isoformat(),
            computed_ms=ms,
        )
        return None
    return ms
