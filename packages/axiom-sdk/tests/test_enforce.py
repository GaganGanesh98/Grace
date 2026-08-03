"""Hard enforcement mode (``enforce=True`` on :func:`axiom.govern`)."""

from __future__ import annotations

import json

import pytest
import responses

import axiom
from axiom.exceptions import GovernanceDenied, GovernanceHeld


@responses.activate
def test_enforce_raises_on_deny(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r-deny",
            "verdict": "deny",
            "reason": "policy",
            "policy_version": "p",
            "risk_assessed": "critical",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    with pytest.raises(GovernanceDenied):
        axiom.govern("a", "t", "https://x", enforce=True)


@responses.activate
def test_enforce_raises_on_hold(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r-hold",
            "verdict": "hold",
            "reason": None,
            "policy_version": "p",
            "risk_assessed": "medium",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    with pytest.raises(GovernanceHeld):
        axiom.govern("a", "t", "https://x", enforce=True)


@responses.activate
def test_enforce_allows_when_verdict_allow(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    responses.add(
        responses.POST,
        f"{base_url}/v1/governance/govern",
        json={
            "receipt_id": "r-ok",
            "verdict": "allow",
            "reason": None,
            "policy_version": "p",
            "risk_assessed": "low",
            "mode": "enforce",
            "chain_id": None,
        },
        status=200,
    )
    r = axiom.govern("a", "t", "https://x", enforce=True)
    assert r.verdict == "allow"
    assert json.loads(responses.calls[0].request.body or b"{}")["risk"] == "low"
