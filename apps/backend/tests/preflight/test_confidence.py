"""Tests for pre-flight confidence helpers."""

from __future__ import annotations

from axiom.services.policy.evaluator import PolicyRule
from axiom.services.preflight.confidence import (
    PreflightConfidence,
    compute_confidence,
    is_rule_deterministic,
)


def test_is_rule_deterministic_none_returns_true() -> None:
    assert is_rule_deterministic(None) is True


def test_is_rule_deterministic_eq_only() -> None:
    rule = PolicyRule(
        id="r",
        description="d",
        when={"type": "chat"},
        then="approve",
    )
    assert is_rule_deterministic(rule) is True


def test_is_rule_deterministic_in_only() -> None:
    rule = PolicyRule(
        id="r",
        description="d",
        when={"type": {"op": "in", "value": ["a", "b"]}},
        then="approve",
    )
    assert is_rule_deterministic(rule) is True


def test_is_rule_deterministic_gt_returns_false() -> None:
    rule = PolicyRule(
        id="r",
        description="d",
        when={"age": {"op": "gt", "value": 18}},
        then="approve",
    )
    assert is_rule_deterministic(rule) is False


def test_is_rule_deterministic_nested_gt_returns_false() -> None:
    rule = PolicyRule(
        id="r",
        description="d",
        when={"outer": {"inner": {"op": "lt", "value": 3}}},
        then="deny",
    )
    assert is_rule_deterministic(rule) is False


def test_compute_confidence_fresh_deterministic() -> None:
    assert (
        compute_confidence(cache_hit=False, cache_age_seconds=0, rule_is_deterministic=True)
        == PreflightConfidence.HIGH
    )


def test_compute_confidence_fresh_nondeterministic() -> None:
    assert (
        compute_confidence(cache_hit=False, cache_age_seconds=0, rule_is_deterministic=False)
        == PreflightConfidence.MEDIUM
    )


def test_compute_confidence_cached_recent() -> None:
    assert (
        compute_confidence(cache_hit=True, cache_age_seconds=60, rule_is_deterministic=True)
        == PreflightConfidence.MEDIUM
    )


def test_compute_confidence_cached_old() -> None:
    assert (
        compute_confidence(cache_hit=True, cache_age_seconds=3600, rule_is_deterministic=True)
        == PreflightConfidence.LOW
    )
