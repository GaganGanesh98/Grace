"""Intent vs execution verification."""

from __future__ import annotations

from uuid import uuid4

from axiom.models.governance import GovernanceIntent
from axiom.services.governance.verification import verify_execution


def _intent() -> GovernanceIntent:
    return GovernanceIntent(
        project_id=uuid4(),
        agent_id="a",
        action_type="tool.http.get",
        target="https://api.example.com/a",
        parameters={},
        risk_declared="low",
        mode="enforce",
        extra_metadata={},
    )


def test_matching_passes() -> None:
    intent = _intent()
    r = verify_execution(
        intent,
        {"target": intent.target, "action_type": intent.action_type, "risk": intent.risk_declared},
    )
    assert r.status == "pass"
    assert r.passed is True
    assert r.mismatches == []


def test_mismatched_target() -> None:
    intent = _intent()
    r = verify_execution(intent, {"target": "https://other", "action_type": intent.action_type})
    assert r.status == "fail"
    assert r.passed is False
    assert any(m["field"] == "target" for m in r.mismatches)


def test_empty_execution_skipped() -> None:
    intent = _intent()
    r = verify_execution(intent, {})
    assert r.status == "skipped"
    assert r.mismatches == []


def test_mismatched_action_type() -> None:
    intent = _intent()
    r = verify_execution(
        intent,
        {"target": intent.target, "action_type": "tool.other", "risk": intent.risk_declared},
    )
    assert r.status == "fail"
    assert any(m["field"] == "action_type" for m in r.mismatches)
