"""Fail-closed JSON policy evaluation (ordered rules, first match wins)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Verdict(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    MODIFY = "modify"
    ESCALATE = "escalate"


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    when: dict[str, Any]
    then: Verdict
    modification: dict[str, Any] | None = None
    escalation_target: str | None = None


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    version: str
    rules: list[PolicyRule]
    default_verdict: Verdict = Field(default=Verdict.DENY)


@dataclass(frozen=True)
class PolicyDecision:
    verdict: Verdict
    rule_id: str | None
    policy_id: str
    policy_version: str
    reasoning: str
    modification: dict[str, Any] | None
    escalation_target: str | None


def _get_path(action: dict[str, Any], field_path: str) -> Any:
    parts = field_path.split(".")
    cur: Any = action
    for part in parts:
        if not isinstance(cur, dict):
            raise KeyError(field_path)
        cur = cur[part]
    return cur


def _eval_predicate(field_path: str, spec: Any, action: dict[str, Any]) -> bool:
    if isinstance(spec, dict) and "op" in spec:
        op = str(spec["op"])
        if op in {"in", "not_in"}:
            choices = spec["value"]
            if not isinstance(choices, list):
                return False
            value = _get_path(action, field_path)
            return value in choices if op == "in" else value not in choices
        value = _get_path(action, field_path)
        rhs = spec.get("value")
        if op == "eq":
            return bool(value == rhs)
        if op == "ne":
            return bool(value != rhs)
        if op == "gt":
            return bool(value > rhs)
        if op == "lt":
            return bool(value < rhs)
        return False
    value = _get_path(action, field_path)
    return bool(value == spec)


def _rule_matches(when: dict[str, Any], action: dict[str, Any]) -> bool:
    return all(_eval_predicate(path, pred, action) for path, pred in when.items())


def evaluate(policy: Policy, action: dict[str, Any]) -> PolicyDecision:
    for rule in policy.rules:
        try:
            matched = _rule_matches(rule.when, action)
        except (KeyError, TypeError, ValueError):
            return PolicyDecision(
                verdict=Verdict.DENY,
                rule_id=None,
                policy_id=policy.id,
                policy_version=policy.version,
                reasoning="evaluation error",
                modification=None,
                escalation_target=None,
            )
        if matched:
            reasoning = f"Matched rule {rule.id}: {rule.description}"
            return PolicyDecision(
                verdict=rule.then,
                rule_id=rule.id,
                policy_id=policy.id,
                policy_version=policy.version,
                reasoning=reasoning,
                modification=rule.modification if rule.then == Verdict.MODIFY else None,
                escalation_target=rule.escalation_target if rule.then == Verdict.ESCALATE else None,
            )
    return PolicyDecision(
        verdict=policy.default_verdict,
        rule_id=None,
        policy_id=policy.id,
        policy_version=policy.version,
        reasoning="No rule matched; applied default verdict",
        modification=None,
        escalation_target=None,
    )
