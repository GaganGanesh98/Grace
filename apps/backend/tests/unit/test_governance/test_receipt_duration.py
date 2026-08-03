"""Phase 7.5.4 — compute_receipt_duration_ms (serialization, not stored)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from axiom.models.governance import GovernanceReceipt
from axiom.services.governance.receipt_duration import compute_receipt_duration_ms


def _sealed_receipt(created: datetime, sealed: datetime | None) -> GovernanceReceipt:
    r = GovernanceReceipt(
        id=uuid4(),
        intent_id=uuid4(),
        verdict_id=uuid4(),
        project_id=uuid4(),
    )
    r.status = "sealed"
    r.created_at = created
    r.sealed_at = sealed
    return r


def test_duration_ms_sealed_rounds_to_nearest_ms() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(milliseconds=1500)
    r = _sealed_receipt(t0, t1)
    assert compute_receipt_duration_ms(r) == 1500


def test_duration_ms_not_sealed_status() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    r = _sealed_receipt(t0, t0 + timedelta(seconds=1))
    r.status = "pending"
    assert compute_receipt_duration_ms(r) is None


def test_duration_ms_sealed_at_null() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    r = _sealed_receipt(t0, None)
    assert compute_receipt_duration_ms(r) is None


def test_duration_ms_negative_guard() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    t1 = t0 - timedelta(seconds=1)
    r = _sealed_receipt(t0, t1)
    assert compute_receipt_duration_ms(r) is None


def test_duration_ms_over_one_hour_guard() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=3601)
    r = _sealed_receipt(t0, t1)
    assert compute_receipt_duration_ms(r) is None
