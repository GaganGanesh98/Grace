"""ExplanationEngine unit tests."""

from __future__ import annotations

from types import SimpleNamespace

from axiom.services.explanation.engine import ExplanationEngine
from axiom.services.policy.evaluator import PolicyDecision, Verdict


def _policy(rules: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(rules=rules)


def test_explain_includes_rule_description() -> None:
    engine = ExplanationEngine()
    pol = _policy([{"id": "r1", "description": "Block outbound PII"}])
    dec = PolicyDecision(
        verdict=Verdict.DENY,
        rule_id="r1",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target=None,
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert "Action denied" in text
    assert "Block outbound PII" in text
    assert "r1" in text


def test_explain_includes_legal_citation_and_remediation() -> None:
    engine = ExplanationEngine()
    pol = _policy(
        [
            {
                "id": "r2",
                "description": "AI hiring tools must be audited",
                "legal_citation": "NYC Local Law 144 § 20-871(a)",
                "remediation_guidance": "Provide bias-audit results before deployment",
            }
        ]
    )
    dec = PolicyDecision(
        verdict=Verdict.DENY,
        rule_id="r2",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target=None,
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert "NYC Local Law 144" in text
    assert "bias-audit" in text


def test_explain_omits_remediation_on_approve() -> None:
    engine = ExplanationEngine()
    pol = _policy([{"id": "r", "description": "Allowed", "remediation_guidance": "unused"}])
    dec = PolicyDecision(
        verdict=Verdict.APPROVE,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target=None,
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert "Action approved" in text
    assert "unused" not in text


def test_explain_fallback_when_rule_missing_metadata() -> None:
    engine = ExplanationEngine()
    pol = _policy([])
    dec = PolicyDecision(
        verdict=Verdict.DENY,
        rule_id="unknown",
        policy_id="p",
        policy_version="1",
        reasoning="fallback",
        modification=None,
        escalation_target=None,
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert "Action denied" in text
    assert "Matched rule unknown" in text


def test_explain_default_fallback_when_no_rule_matched() -> None:
    engine = ExplanationEngine()
    pol = _policy([])
    dec = PolicyDecision(
        verdict=Verdict.DENY,
        rule_id=None,
        policy_id="p",
        policy_version="1",
        reasoning="No rule matched; applied default verdict",
        modification=None,
        escalation_target=None,
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert "Applied policy default" in text


def test_explain_escalate_includes_target() -> None:
    engine = ExplanationEngine()
    pol = _policy([{"id": "r", "description": "needs review"}])
    dec = PolicyDecision(
        verdict=Verdict.ESCALATE,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target="ops-team",
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert "escalated" in text.lower()
    assert "ops-team" in text


def test_explain_length_bounded() -> None:
    engine = ExplanationEngine()
    huge = "x" * 5000
    pol = _policy(
        [{"id": "r", "description": huge, "legal_citation": huge, "remediation_guidance": huge}]
    )
    dec = PolicyDecision(
        verdict=Verdict.DENY,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification=None,
        escalation_target=None,
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert len(text) <= 1000


def test_explain_no_policy() -> None:
    engine = ExplanationEngine()
    text = engine.explain_no_policy()
    assert "No policy" in text
    assert "fails closed" in text.lower()


def test_explain_modify_verdict() -> None:
    engine = ExplanationEngine()
    pol = _policy([{"id": "r", "description": "trim PII"}])
    dec = PolicyDecision(
        verdict=Verdict.MODIFY,
        rule_id="r",
        policy_id="p",
        policy_version="1",
        reasoning="r",
        modification={"redact": True},
        escalation_target=None,
    )
    text = engine.explain(dec, pol)  # type: ignore[arg-type]
    assert "approved with required modifications" in text
