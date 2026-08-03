"""Tests for :mod:`axiom.policy_suggester`."""

from __future__ import annotations

import yaml

from axiom.policy_suggester import evaluate_policy, suggest_policy


def _yaml_doc(yml: str) -> dict:
    body = "\n".join(line for line in yml.splitlines() if not line.strip().startswith("#"))
    doc = yaml.safe_load(body)
    assert isinstance(doc, dict)
    return doc


def test_suggest_allows_llm_calls() -> None:
    report = {
        "agent_id": "a",
        "calls": [
            {
                "action_type": "tool.llm.openai",
                "target": "api.openai.com/v1/chat/completions",
                "risk": "low",
                "verdict": "allow",
            }
        ],
    }
    doc = _yaml_doc(suggest_policy(report))
    v = evaluate_policy(doc, "tool.llm.openai", "api.openai.com/v1/chat/completions", "low")
    assert v == "allow"


def test_suggest_holds_email_calls() -> None:
    report = {
        "agent_id": "a",
        "calls": [
            {
                "action_type": "tool.email.send",
                "target": "smtp.gmail.com/",
                "risk": "high",
                "verdict": "allow",
            }
        ],
    }
    doc = _yaml_doc(suggest_policy(report))
    v = evaluate_policy(doc, "tool.email.send", "smtp.gmail.com/", "high")
    assert v == "hold"


def test_suggest_denies_by_default() -> None:
    report = {
        "agent_id": "a",
        "calls": [
            {
                "action_type": "tool.unknown",
                "target": "evil.com/",
                "risk": "low",
                "verdict": "allow",
            }
        ],
    }
    doc = _yaml_doc(suggest_policy(report))
    v = evaluate_policy(doc, "tool.unknown", "evil.com/", "low")
    assert v == "deny"


def test_suggest_generates_valid_yaml() -> None:
    report: dict = {"agent_id": "x", "calls": []}
    doc = _yaml_doc(suggest_policy(report))
    assert "rules" in doc


def test_suggest_handles_empty_report() -> None:
    doc = _yaml_doc(suggest_policy({}))
    assert str(doc["name"]).endswith("-policy")


def test_suggest_deduplicates_rules() -> None:
    report = {
        "agent_id": "a",
        "calls": [
            {"action_type": "tool.llm.openai", "target": "a", "risk": "low", "verdict": "allow"},
            {"action_type": "tool.llm.openai", "target": "b", "risk": "low", "verdict": "allow"},
        ],
    }
    doc = _yaml_doc(suggest_policy(report))
    llm_rules = [
        r
        for r in doc["rules"]
        if isinstance(r, dict) and "tool.llm.openai" in str(r.get("condition", ""))
    ]
    assert len(llm_rules) == 1
