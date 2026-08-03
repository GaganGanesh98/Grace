"""Policy evaluation and active-policy description (YAML-backed)."""

from __future__ import annotations

from uuid import UUID

import pytest

import axiom.services.governance.policy as policy_mod
from axiom.db import session_scope
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import (
    clear_policy_cache_for_tests,
    describe_active_governance_policy,
    evaluate_policy,
)
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.fixture(autouse=True)
def _clear_policy_cache() -> None:
    clear_policy_cache_for_tests()
    yield
    clear_policy_cache_for_tests()


def test_describe_active_returns_read_only_when_configured() -> None:
    meta = describe_active_governance_policy({"governance_policy": "read-only"})
    assert meta["name"] == "read-only"
    assert meta["is_default_configuration"] is False
    assert any(r.get("name") == "allow-all" for r in meta["rules"])


@pytest.mark.asyncio
async def test_describe_active_default_is_starter_safe_when_unset() -> None:
    meta = describe_active_governance_policy(None)
    assert meta["name"] == "starter-safe"
    assert meta["is_default_configuration"] is True
    assert meta["display_name"]


@pytest.mark.asyncio
async def test_evaluate_policy_denies_critical_starter_safe(client) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        req = GovernRequest(
            agent_id="a",
            action_type="tool.any",
            target="https://x",
            risk="critical",
        )
        intent = await declare_intent(session, pid, req)
        ctx = {"project_settings": dict(project.settings or {})}
        pr = evaluate_policy(intent, ctx)
        assert pr.verdict == "deny"
        assert pr.reason is not None


@pytest.mark.asyncio
async def test_evaluate_policy_holds_high_risk_starter_safe(client) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        req = GovernRequest(
            agent_id="a",
            action_type="tool.any",
            target="https://x",
            risk="high",
        )
        intent = await declare_intent(session, pid, req)
        ctx = {"project_settings": dict(project.settings or {})}
        pr = evaluate_policy(intent, ctx)
        assert pr.verdict == "hold"


@pytest.mark.asyncio
async def test_evaluate_policy_allows_low_risk_starter_safe(client) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        s = dict(project.settings or {})
        s["governance_policy"] = "starter-safe"
        project.settings = s
        req = GovernRequest(
            agent_id="a",
            action_type="tool.http.get",
            target="https://z",
            risk="low",
        )
        intent = await declare_intent(session, pid, req)
        ctx = {"project_settings": dict(project.settings or {})}
        pr = evaluate_policy(intent, ctx)
        assert pr.verdict == "allow"


@pytest.mark.asyncio
async def test_evaluate_policy_unknown_action_no_rule_match_holds(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _real = policy_mod._load_policy_yaml

    def _narrow_policy(stem: str) -> dict:
        if stem == "read-only":
            return {
                "version": 1,
                "name": "Narrow",
                "rules": [
                    {
                        "name": "only-specific",
                        "condition": "action_type == 'only.registered'",
                        "verdict": "allow",
                        "reason": None,
                    },
                ],
            }
        return _real(stem)

    monkeypatch.setattr(policy_mod, "_load_policy_yaml", _narrow_policy)
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        req = GovernRequest(
            agent_id="a",
            action_type="completely.unknown.action",
            target="https://x",
            risk="low",
        )
        intent = await declare_intent(session, pid, req)
        ctx = {"project_settings": {"governance_policy": "read-only"}}
        pr = evaluate_policy(intent, ctx)
        assert pr.verdict == "hold"
        assert "No rule matched" in (pr.reason or "")


@pytest.mark.asyncio
async def test_evaluate_policy_malformed_yaml_fails_closed_to_starter_safe(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _real = policy_mod._load_policy_yaml

    def _boom(stem: str) -> dict:
        if stem == "read-only":
            raise ValueError("simulated corrupt policy")
        return _real(stem)

    monkeypatch.setattr(policy_mod, "_load_policy_yaml", _boom)
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    pid = UUID(fx["project_id"])
    async with session_scope() as session:
        project = await session.get(Project, pid)
        assert project is not None
        req = GovernRequest(
            agent_id="a",
            action_type="tool.http.get",
            target="https://safe.example",
            risk="low",
        )
        intent = await declare_intent(session, pid, req)
        ctx = {"project_settings": {"governance_policy": "read-only"}}
        pr = evaluate_policy(intent, ctx)
        assert pr.verdict == "allow"
        assert "starter-safe" in pr.policy_version
