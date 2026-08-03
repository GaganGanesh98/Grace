"""Unit tests for :mod:`axiom.client` (HTTP mocked with ``responses``)."""

from __future__ import annotations

import json
from unittest import mock

import pytest
import responses

import axiom
from axiom.exceptions import AuthError, AxiomError, GovernanceDenied, GovernanceHeld


@responses.activate
def test_govern_allow(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r1",
            "verdict": "allow",
            "reason": None,
            "policy_version": "p1",
            "risk_assessed": "low",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    r = axiom.govern("a1", "tool.x", "https://t", risk="low")
    assert r.verdict == "allow"
    assert r.receipt_id == "r1"
    assert r.chain_id is None
    assert r.policy_version == "p1"
    assert r.risk_assessed == "low"
    assert r.raw["mode"] == "enforce"


@responses.activate
def test_govern_deny_no_enforce(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r2",
            "verdict": "deny",
            "reason": "blocked",
            "policy_version": "p1",
            "risk_assessed": "high",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    r = axiom.govern("a1", "tool.x", "https://t", enforce=False)
    assert r.verdict == "deny"
    assert r.reason == "blocked"


@responses.activate
def test_govern_deny_with_enforce(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r3",
            "verdict": "deny",
            "reason": "no",
            "policy_version": "p1",
            "risk_assessed": "high",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    with pytest.raises(GovernanceDenied) as ei:
        axiom.govern("a1", "tool.x", "https://t", enforce=True)
    assert ei.value.receipt_id == "r3"
    assert ei.value.verdict == "deny"


@responses.activate
def test_govern_hold_with_enforce(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r4",
            "verdict": "hold",
            "reason": "approval",
            "policy_version": "p1",
            "risk_assessed": "medium",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    with pytest.raises(GovernanceHeld) as ei:
        axiom.govern("a1", "tool.x", "https://t", enforce=True)
    assert ei.value.receipt_id == "r4"


@responses.activate
def test_report_sealed(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/report",
        json={
            "receipt_id": "r1",
            "status": "sealed",
            "verification": "pass",
            "signatures": {"ed25519": True, "ml_dsa_65": True},
            "merkle": {"leaf": "a", "root": "b"},
        },
        status=200,
    )
    out = axiom.report("r1", {"target": "https://x", "action_type": "t", "risk": "low"})
    assert out.status == "sealed"
    assert out.verification == "pass"
    assert out.signatures["ed25519"] is True
    assert out.merkle["root"] == "b"


@responses.activate
def test_verify_valid(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    rid = "550e8400-e29b-41d4-a716-446655440001"
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/verify",
        json={
            "valid": True,
            "checks": {"ed25519": True, "ml_dsa_65": True, "merkle": True},
            "errors": [],
        },
        status=200,
    )
    v = axiom.verify(rid)
    assert v.valid is True
    assert v.checks["merkle"] is True
    assert v.receipt_id == rid
    body = json.loads(responses.calls[0].request.body or b"{}")
    assert body == {"receipt_id": rid}


@responses.activate
def test_verify_invalid(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    rid = "550e8400-e29b-41d4-a716-446655440001"
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/verify",
        json={
            "valid": False,
            "checks": {"ed25519": False, "ml_dsa_65": True, "merkle": True},
            "errors": ["ed25519"],
        },
        status=200,
    )
    v = axiom.verify(rid)
    assert v.valid is False
    assert v.checks["ed25519"] is False


@responses.activate
def test_close_chain(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    cid = "990e8400-e29b-41d4-a716-446655440005"
    responses.add(
        responses.POST,
        f"{base_url}/v1/chains/{cid}/close",
        json={
            "id": cid,
            "workflow_name": "wf",
            "agent_id": "a1",
            "status": "sealed",
            "total_actions": 3,
            "authorized": 2,
            "held": 1,
            "denied": 0,
            "compliant": 2,
            "non_compliant": 0,
            "compliance_rate": 66.6,
            "chain_signature": {"ed25519": True, "ml_dsa_65": True},
            "started_at": "2026-01-01T00:00:00+00:00",
            "closed_at": "2026-01-01T00:01:00+00:00",
            "sealed_at": "2026-01-01T00:01:00+00:00",
            "records": [],
        },
        status=200,
    )
    out = axiom.close_chain(cid)
    assert out.chain_id == cid
    assert out.status == "sealed"
    assert out.total_actions == 3
    assert out.authorized == 2
    assert out.held == 1
    assert out.denied == 0


@responses.activate
def test_auth_error(base_url: str) -> None:
    axiom.init(api_key="bad", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        body="Unauthorized",
        status=401,
    )
    with pytest.raises(AuthError):
        axiom.govern("a", "t", "https://x")


@responses.activate
def test_api_error(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={"detail": "boom"},
        status=500,
    )
    with pytest.raises(AxiomError) as ei:
        axiom.govern("a", "t", "https://x")
    assert "500" in str(ei.value)


def test_init_required() -> None:
    with pytest.raises(RuntimeError, match="axiom.init"):
        axiom.govern("a", "t", "https://x")


@responses.activate
def test_govern_with_workflow(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r1",
            "verdict": "allow",
            "reason": None,
            "policy_version": "p",
            "risk_assessed": "low",
            "mode": "enforce",
            "chain_id": "c1",
        },
        status=200,
    )
    axiom.govern("a1", "tool.x", "https://t", workflow="wf-1")
    body = json.loads(responses.calls[0].request.body or b"{}")
    assert body["workflow"] == "wf-1"


@responses.activate
def test_govern_with_chain_id(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r1",
            "verdict": "allow",
            "reason": None,
            "policy_version": "p",
            "risk_assessed": "low",
            "mode": "enforce",
            "chain_id": "chain-xyz",
        },
        status=200,
    )
    axiom.govern("a1", "tool.x", "https://t", chain_id="chain-xyz")
    body = json.loads(responses.calls[0].request.body or b"{}")
    assert body["chain_id"] == "chain-xyz"


@responses.activate
def test_user_agent_includes_sdk_version(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r1",
            "verdict": "allow",
            "reason": None,
            "policy_version": "p",
            "risk_assessed": "low",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    axiom.govern("a", "t", "https://x")
    ua = responses.calls[0].request.headers.get("User-Agent", "")
    assert ua.startswith("axiom-sdk-python/")
    assert axiom.__version__ in ua


@responses.activate
def test_get_receipt_returns_approval_fields(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    rid = "550e8400-e29b-41d4-a716-446655440099"
    responses.add(
        responses.GET,
        f"{base_url}/v1/governance/receipts/{rid}",
        json={
            "id": rid,
            "intent": {},
            "verdict": {"verdict": "hold", "reason": "wait", "policy_version": "p", "rules_evaluated": [], "risk_assessed": "high", "context": {}, "created_at": "2026-01-01T00:00:00Z"},
            "execution": None,
            "verification": {"status": "pending", "mismatches": []},
            "signatures": {"ed25519": "", "ml_dsa_65": "", "key_id": ""},
            "merkle": {"leaf": "", "root": "", "depth": 0, "path": []},
            "policy_version": "p",
            "sealed_at": None,
            "status": "pending",
            "signer_public": None,
            "approval_status": "pending",
            "approved_by": None,
            "approved_at": None,
            "approval_reason": None,
            "approval_expires_at": "2026-01-01T00:30:00Z",
        },
        status=200,
    )
    r = axiom.get_receipt(rid)
    assert r.verdict == "hold"
    assert r.approval_status == "pending"
    assert r.reason == "wait"


@responses.activate
def test_wait_for_decision_returns_on_allow(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    rid = "550e8400-e29b-41d4-a716-446655440088"
    hold_body = {
        "id": rid,
        "intent": {},
        "verdict": {"verdict": "hold", "reason": None, "policy_version": "p", "rules_evaluated": [], "risk_assessed": "high", "context": {}, "created_at": "2026-01-01T00:00:00Z"},
        "execution": None,
        "verification": {"status": "pending", "mismatches": []},
        "signatures": {"ed25519": "", "ml_dsa_65": "", "key_id": ""},
        "merkle": {"leaf": "", "root": "", "depth": 0, "path": []},
        "policy_version": "p",
        "sealed_at": None,
        "status": "pending",
        "signer_public": None,
        "approval_status": "pending",
        "approved_by": None,
        "approved_at": None,
        "approval_reason": None,
        "approval_expires_at": None,
    }
    allow_body = {**hold_body, "verdict": {**hold_body["verdict"], "verdict": "allow"}, "approval_status": "approved"}
    responses.add(responses.GET, f"{base_url}/v1/governance/receipts/{rid}", json=hold_body, status=200)
    responses.add(responses.GET, f"{base_url}/v1/governance/receipts/{rid}", json=allow_body, status=200)
    with mock.patch("axiom.time.sleep", autospec=True):
        out = axiom.wait_for_decision(rid, poll_interval=0.01, timeout=5.0)
    assert out.verdict == "allow"


@responses.activate
def test_wait_for_decision_times_out(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    rid = "550e8400-e29b-41d4-a716-446655440077"
    hold_body = {
        "id": rid,
        "intent": {},
        "verdict": {"verdict": "hold", "reason": None, "policy_version": "p", "rules_evaluated": [], "risk_assessed": "high", "context": {}, "created_at": "2026-01-01T00:00:00Z"},
        "execution": None,
        "verification": {"status": "pending", "mismatches": []},
        "signatures": {"ed25519": "", "ml_dsa_65": "", "key_id": ""},
        "merkle": {"leaf": "", "root": "", "depth": 0, "path": []},
        "policy_version": "p",
        "sealed_at": None,
        "status": "pending",
        "signer_public": None,
        "approval_status": "pending",
        "approved_by": None,
        "approved_at": None,
        "approval_reason": None,
        "approval_expires_at": None,
    }
    responses.add(responses.GET, f"{base_url}/v1/governance/receipts/{rid}", json=hold_body, status=200)
    with mock.patch("axiom.time.sleep", autospec=True):
        with pytest.raises(TimeoutError):
            axiom.wait_for_decision(rid, poll_interval=0.01, timeout=0.05)


@responses.activate
def test_wait_for_decision_polls_until_deny(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    rid = "550e8400-e29b-41d4-a716-446655440066"
    hold_body = {
        "id": rid,
        "intent": {},
        "verdict": {"verdict": "hold", "reason": None, "policy_version": "p", "rules_evaluated": [], "risk_assessed": "high", "context": {}, "created_at": "2026-01-01T00:00:00Z"},
        "execution": None,
        "verification": {"status": "pending", "mismatches": []},
        "signatures": {"ed25519": "", "ml_dsa_65": "", "key_id": ""},
        "merkle": {"leaf": "", "root": "", "depth": 0, "path": []},
        "policy_version": "p",
        "sealed_at": None,
        "status": "pending",
        "signer_public": None,
        "approval_status": "pending",
        "approved_by": None,
        "approved_at": None,
        "approval_reason": None,
        "approval_expires_at": None,
    }
    deny_body = {**hold_body, "verdict": {**hold_body["verdict"], "verdict": "deny"}, "approval_status": "rejected"}
    responses.add(responses.GET, f"{base_url}/v1/governance/receipts/{rid}", json=hold_body, status=200)
    responses.add(responses.GET, f"{base_url}/v1/governance/receipts/{rid}", json=deny_body, status=200)
    with mock.patch("axiom.time.sleep", autospec=True):
        out = axiom.wait_for_decision(rid, poll_interval=0.01, timeout=5.0)
    assert out.verdict == "deny"
