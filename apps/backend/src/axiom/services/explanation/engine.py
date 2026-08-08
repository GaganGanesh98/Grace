"""Deterministic explanation engine.

Composes a human-readable sentence from a ``PolicyDecision`` + matched rule
metadata. Produces the "why" that WEDGEs AXIOM against GaaS's thin,
LLM-generated blurbs: our explanation cites the policy rule, the legal
citation (when the rule author provided one), and practical remediation
guidance.

The rule metadata contract (optional fields we look for on each rule dict):

  * ``legal_citation``       e.g. ``"NYC Local Law 144 § 20-871(a)"``
  * ``citation_url``         e.g. ``"https://..."``
  * ``remediation_guidance`` e.g. ``"Provide bias-audit results..."``
  * ``description``          (already required by the evaluator)

Output is capped at 1000 characters to keep UIs readable; when a citation
pushes us over the cap we drop the remediation first, then the citation.
"""

from __future__ import annotations

from typing import Any

from axiom.models.policy import Policy as PolicyModel
from axiom.services.policy.evaluator import PolicyDecision, Verdict

_MAX_LENGTH = 1000

_VERDICT_PHRASING: dict[Verdict, str] = {
    Verdict.APPROVE: "Action approved",
    Verdict.DENY: "Action denied",
    Verdict.MODIFY: "Action approved with required modifications",
    Verdict.ESCALATE: "Action escalated for human review",
}


def _find_rule(policy: PolicyModel, rule_id: str | None) -> dict[str, Any] | None:
    if rule_id is None:
        return None
    raw = policy.rules if isinstance(policy.rules, list) else []
    for item in raw:
        if isinstance(item, dict) and item.get("id") == rule_id:
            return item
    return None


def _truncate(text: str) -> str:
    if len(text) <= _MAX_LENGTH:
        return text
    return text[: _MAX_LENGTH - 1].rstrip() + "…"


class ExplanationEngine:
    """Stateless. Safe to reuse across requests."""

    def explain(self, decision: PolicyDecision, policy: PolicyModel) -> str:
        verdict_phrase = _VERDICT_PHRASING.get(decision.verdict, "Verdict issued")
        rule = _find_rule(policy, decision.rule_id)

        head = verdict_phrase + "."
        parts: list[str] = [head]

        if rule is not None:
            description = str(rule.get("description") or "").strip()
            rule_id = str(rule.get("id") or "").strip()
            if description:
                if rule_id:
                    parts.append(f"Rule {rule_id}: {description}.")
                else:
                    parts.append(f"Rule: {description}.")
            citation = str(rule.get("legal_citation") or "").strip()
            if citation:
                parts.append(f"Governing authority: {citation}.")
            remediation = str(rule.get("remediation_guidance") or "").strip()
            if remediation and decision.verdict != Verdict.APPROVE:
                parts.append(f"To remediate: {remediation}.")
        elif decision.rule_id:
            parts.append(f"Matched rule {decision.rule_id}.")
        else:
            parts.append(f"Applied policy default: {decision.reasoning}.")

        if decision.verdict == Verdict.ESCALATE and decision.escalation_target:
            parts.append(f"Escalated to: {decision.escalation_target}.")

        full = " ".join(parts).strip()
        return _truncate(full)

    def explain_no_policy(self) -> str:
        return (
            "Action denied. No policy is configured for this project; "
            "Grace fails closed when no rule is in effect. "
            "To remediate: configure at least one active policy for this project "
            "before calling /v1/govern."
        )
