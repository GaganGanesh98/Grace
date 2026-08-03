"""Tests for fail-closed policy evaluation."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from axiom.services.policy.evaluator import Policy, PolicyRule, Verdict, evaluate


def test_empty_rules_returns_default_deny() -> None:
    p = Policy(id="p1", name="n", version="1.0.0", rules=[])
    d = evaluate(p, {})
    assert d.verdict == Verdict.DENY
    assert d.rule_id is None


def test_first_matching_rule_wins() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(id="r1", description="first", when={"x": 1}, then=Verdict.APPROVE),
            PolicyRule(id="r2", description="second", when={"x": 1}, then=Verdict.DENY),
        ],
    )
    d = evaluate(p, {"x": 1})
    assert d.verdict == Verdict.APPROVE
    assert d.rule_id == "r1"


def test_no_matching_rule_returns_default() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[PolicyRule(id="r1", description="d", when={"x": 1}, then=Verdict.APPROVE)],
        default_verdict=Verdict.ESCALATE,
    )
    d = evaluate(p, {"x": 2})
    assert d.verdict == Verdict.ESCALATE
    assert d.rule_id is None


def test_eq_operator() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"n": {"op": "eq", "value": 3}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"n": 3}).verdict == Verdict.APPROVE
    assert evaluate(p, {"n": 4}).verdict == Verdict.DENY


def test_ne_operator() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"n": {"op": "ne", "value": 0}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"n": 1}).verdict == Verdict.APPROVE
    assert evaluate(p, {"n": 0}).verdict == Verdict.DENY


def test_in_operator() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"role": {"op": "in", "value": ["a", "b"]}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"role": "a"}).verdict == Verdict.APPROVE
    assert evaluate(p, {"role": "c"}).verdict == Verdict.DENY


def test_in_operator_requires_list_value() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"role": {"op": "in", "value": "admin"}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"role": "admin"}).verdict == Verdict.DENY


def test_not_in_operator() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"role": {"op": "not_in", "value": ["blocked"]}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"role": "ok"}).verdict == Verdict.APPROVE
    assert evaluate(p, {"role": "blocked"}).verdict == Verdict.DENY


def test_gt_operator() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"n": {"op": "gt", "value": 2}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"n": 3}).verdict == Verdict.APPROVE
    assert evaluate(p, {"n": 2}).verdict == Verdict.DENY


def test_unknown_operator_returns_no_match() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"n": {"op": "bogus", "value": 1}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"n": 1}).verdict == Verdict.DENY


def test_lt_operator() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"n": {"op": "lt", "value": 5}},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"n": 1}).verdict == Verdict.APPROVE
    assert evaluate(p, {"n": 5}).verdict == Verdict.DENY


def test_nested_path_non_dict_intermediate_returns_deny() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"user.role": "admin"},
                then=Verdict.APPROVE,
            )
        ],
    )
    d = evaluate(p, {"user": "not-a-dict"})
    assert d.verdict == Verdict.DENY
    assert d.reasoning == "evaluation error"


def test_nested_field_path() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"user.role": "admin"},
                then=Verdict.APPROVE,
            )
        ],
    )
    assert evaluate(p, {"user": {"role": "admin"}}).verdict == Verdict.APPROVE
    assert evaluate(p, {"user": {"role": "guest"}}).verdict == Verdict.DENY


def test_modify_verdict_includes_modification() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"x": 1},
                then=Verdict.MODIFY,
                modification={"patch": True},
            )
        ],
    )
    d = evaluate(p, {"x": 1})
    assert d.verdict == Verdict.MODIFY
    assert d.modification == {"patch": True}


def test_escalate_verdict_includes_target() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"x": 1},
                then=Verdict.ESCALATE,
                escalation_target="security@example.com",
            )
        ],
    )
    d = evaluate(p, {"x": 1})
    assert d.verdict == Verdict.ESCALATE
    assert d.escalation_target == "security@example.com"


def test_exception_during_evaluation_returns_deny() -> None:
    p = Policy(
        id="p1",
        name="n",
        version="1.0.0",
        rules=[
            PolicyRule(
                id="r1",
                description="d",
                when={"n": {"op": "gt", "value": 1}},
                then=Verdict.APPROVE,
            )
        ],
    )
    d = evaluate(p, {"n": "not-a-number"})
    assert d.verdict == Verdict.DENY
    assert d.reasoning == "evaluation error"


def test_policy_validates_via_pydantic() -> None:
    with pytest.raises(ValidationError):
        Policy.model_validate(
            {
                "id": "p",
                "name": "n",
                "version": "1.0.0",
                "rules": [],
                "extra_field": 1,
            }
        )


def test_verdict_enum_serializable() -> None:
    raw = json.dumps({"v": Verdict.APPROVE.value})
    assert json.loads(raw)["v"] == "approve"
