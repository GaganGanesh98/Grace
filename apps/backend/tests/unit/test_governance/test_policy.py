"""YAML policy evaluation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from axiom.models.governance import GovernanceIntent
from axiom.services.governance.policy import (
    PolicyResult,
    clear_policy_cache_for_tests,
    evaluate_policy,
)


def _intent(*, risk: str = "low") -> GovernanceIntent:
    return GovernanceIntent(
        project_id=uuid4(),
        agent_id="a1",
        action_type="tool.x",
        target="https://t",
        parameters={},
        risk_declared=risk,
        mode="enforce",
        extra_metadata={},
    )


@pytest.fixture(autouse=True)
def _clear_policy_cache() -> None:
    clear_policy_cache_for_tests()
    yield
    clear_policy_cache_for_tests()


def test_starter_safe_risk_paths() -> None:
    ctx = {"project_settings": {"governance_policy": "starter-safe"}}
    assert evaluate_policy(_intent(risk="low"), ctx).verdict == "allow"
    assert evaluate_policy(_intent(risk="medium"), ctx).verdict == "allow"
    assert evaluate_policy(_intent(risk="high"), ctx).verdict == "hold"
    assert evaluate_policy(_intent(risk="critical"), ctx).verdict == "deny"


def test_approval_first_holds_except_critical_denies() -> None:
    ctx = {"project_settings": {"governance_policy": "approval-first"}}
    assert evaluate_policy(_intent(risk="critical"), ctx).verdict == "deny"
    for r in ("low", "medium", "high"):
        res = evaluate_policy(_intent(risk=r), ctx)
        assert res.verdict == "hold"


def test_read_only_allows() -> None:
    ctx = {"project_settings": {"governance_policy": "read-only"}}
    assert evaluate_policy(_intent(risk="critical"), ctx).verdict == "allow"


def test_unknown_policy_falls_back_to_starter_safe() -> None:
    ctx = {"project_settings": {"governance_policy": "does-not-exist-xyz"}}
    res = evaluate_policy(_intent(risk="low"), ctx)
    assert res.verdict == "allow"
    assert "starter-safe" in res.policy_version


def test_empty_rules_holds() -> None:
    """Policy file with no matching rules ends in default hold."""
    ctx = {"project_settings": {"governance_policy": "starter-safe"}}
    intent = _intent(risk="low")
    intent.risk_declared = "unknown-tier"
    res = evaluate_policy(intent, ctx)
    assert isinstance(res, PolicyResult)
    assert res.verdict == "hold"
