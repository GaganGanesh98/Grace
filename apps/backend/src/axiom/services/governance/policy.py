"""Stage 3: policy evaluation (YAML rules, first match wins)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from axiom.models.governance import GovernanceIntent

_POLICIES_DIR = Path(__file__).resolve().parents[4] / "policies"
_CACHE: dict[str, dict[str, Any]] = {}


def clear_policy_cache_for_tests() -> None:
    _CACHE.clear()


def _resolve_policy_stem(requested: str) -> str:
    stem = requested.strip() or "starter-safe"
    if (_POLICIES_DIR / f"{stem}.yaml").is_file():
        return stem
    return "starter-safe"


@dataclass(frozen=True)
class PolicyResult:
    verdict: str
    reason: str | None
    policy_version: str
    rules_evaluated: list[dict[str, Any]]
    risk_assessed: str


def _load_policy_yaml(stem: str) -> dict[str, Any]:
    if stem in _CACHE:
        return _CACHE[stem]
    path = _POLICIES_DIR / f"{stem}.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        msg = "invalid policy yaml"
        raise ValueError(msg)
    _CACHE[stem] = data
    return data


def _eval_condition(condition: str, intent: GovernanceIntent, _context: dict) -> bool:
    c = condition.strip()
    if c == "true":
        return True
    if "==" not in c:
        return False
    left, right = c.split("==", 1)
    left = left.strip()
    right = right.strip().strip("\"'")
    if left == "risk":
        return intent.risk_declared == right
    if left == "action_type":
        return intent.action_type == right
    if left == "target":
        return intent.target == right
    return False


def _rule_result(verdict: str, *, matched: bool) -> str:
    if not matched:
        return "no_match"
    return verdict


def describe_active_governance_policy(project_settings: dict[str, Any] | None) -> dict[str, Any]:
    """Return active governance YAML policy metadata for a project (config-based).

    Used by GET /v1/governance/policies/active. Does not require any receipts.
    """
    settings = project_settings or {}
    raw = settings.get("governance_policy")
    explicit = raw is not None and (not isinstance(raw, str) or bool(str(raw).strip()))
    requested = str(raw or "starter-safe").strip() or "starter-safe"
    stem = _resolve_policy_stem(requested if explicit else "starter-safe")
    try:
        doc = _load_policy_yaml(stem)
    except (OSError, ValueError, yaml.YAMLError):
        stem = "starter-safe"
        doc = _load_policy_yaml(stem)

    ver = int(doc.get("version") or 1)
    version_label = f"{ver}.0"
    display = str(doc.get("name") or stem.replace("-", " ").title())
    rules_raw = doc.get("rules") or []
    rules_out: list[dict[str, Any]] = []
    if isinstance(rules_raw, list):
        for rule in rules_raw:
            if isinstance(rule, dict):
                rules_out.append(
                    {
                        "name": str(rule.get("name") or ""),
                        "condition": str(rule.get("condition") or ""),
                        "verdict": str(rule.get("verdict") or ""),
                        "reason": rule.get("reason"),
                    }
                )
    is_default_configuration = not explicit
    return {
        "name": stem,
        "display_name": display,
        "version": version_label,
        "rules": rules_out,
        "is_default_configuration": is_default_configuration,
    }


def evaluate_policy(intent: GovernanceIntent, context: dict) -> PolicyResult:
    settings = context.get("project_settings") or {}
    requested = str(settings.get("governance_policy") or "starter-safe")
    stem = _resolve_policy_stem(requested)
    try:
        doc = _load_policy_yaml(stem)
    except (OSError, ValueError, yaml.YAMLError):
        stem = "starter-safe"
        doc = _load_policy_yaml(stem)

    version = int(doc.get("version") or 1)
    policy_version = f"{stem}-v{version}"
    rules = doc.get("rules") or []
    rules_evaluated: list[dict[str, Any]] = []
    risk_assessed = intent.risk_declared

    if not isinstance(rules, list):
        rules = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rname = str(rule.get("name") or "anonymous")
        cond = str(rule.get("condition") or "false")
        matched = _eval_condition(cond, intent, context)
        verdict = str(rule.get("verdict") or "hold")
        reason = rule.get("reason")
        reason_s = str(reason) if reason is not None else None
        rules_evaluated.append(
            {
                "rule_name": rname,
                "matched": matched,
                "result": _rule_result(verdict, matched=matched),
            }
        )
        if matched:
            return PolicyResult(
                verdict=verdict,
                reason=reason_s,
                policy_version=policy_version,
                rules_evaluated=rules_evaluated,
                risk_assessed=risk_assessed,
            )

    return PolicyResult(
        verdict="hold",
        reason=f"No rule matched in policy {stem!r}",
        policy_version=policy_version,
        rules_evaluated=rules_evaluated,
        risk_assessed=risk_assessed,
    )
