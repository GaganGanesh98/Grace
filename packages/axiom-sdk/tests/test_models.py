"""Dataclass and helper behavior tests."""

from __future__ import annotations

import pytest

from axiom.exceptions import GovernanceDenied
from axiom.models import GovernResult


def test_require_allow_helper() -> None:
    ok = GovernResult(
        verdict="allow",
        receipt_id="r1",
        chain_id=None,
        reason=None,
        policy_version="p",
        risk_assessed="low",
        raw={},
    )
    ok.require_allow()

    deny = GovernResult(
        verdict="deny",
        receipt_id="r2",
        chain_id=None,
        reason="nope",
        policy_version="p",
        risk_assessed="high",
        raw={},
    )
    with pytest.raises(GovernanceDenied) as ei:
        deny.require_allow()
    assert ei.value.receipt_id == "r2"
    assert ei.value.verdict == "deny"

    hold = GovernResult(
        verdict="hold",
        receipt_id="r3",
        chain_id=None,
        reason="wait",
        policy_version="p",
        risk_assessed="medium",
        raw={},
    )
    with pytest.raises(GovernanceDenied) as ei:
        hold.require_allow()
    assert ei.value.verdict == "hold"


def test_report_result_fields() -> None:
    from axiom.models import ReportResult

    r = ReportResult(
        receipt_id="x",
        status="sealed",
        verification="pass",
        signatures={"ed25519": True},
        merkle={"root": "a"},
        raw={"extra": 1},
    )
    assert r.raw["extra"] == 1
