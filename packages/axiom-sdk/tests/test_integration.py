"""Integration tests against a running AXIOM API (default http://127.0.0.1:8000)."""

from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

import axiom

BASE = os.environ.get("AXIOM_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _reachable() -> bool:
    try:
        r = requests.get(f"{BASE}/healthz", timeout=2)
        return r.status_code == 200
    except OSError:
        return False


@pytest.fixture(scope="module")
def _require_backend() -> None:
    if not _reachable():
        pytest.skip("AXIOM API not reachable (start the backend or set AXIOM_BASE_URL)")


@pytest.fixture(scope="module")
def integration_ctx(_require_backend: None) -> dict[str, str]:
    email = f"sdk-int-{uuid.uuid4().hex[:12]}@example.com"
    password = "password1a"

    su = requests.post(
        f"{BASE}/api/v1/auth/signup",
        json={"email": email, "password": password, "full_name": "SDK Int"},
        timeout=30,
    )
    assert su.status_code == 201, su.text
    access = su.json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {access}"}
    time.sleep(0.2)

    slug = f"sdk-{uuid.uuid4().hex[:8]}"
    pr = requests.post(
        f"{BASE}/api/v1/projects",
        headers=h,
        json={"name": "SDK Integration", "slug": slug},
        timeout=30,
    )
    assert pr.status_code == 201, pr.text
    project_id = pr.json()["data"]["id"]
    time.sleep(0.2)

    kr = requests.post(
        f"{BASE}/api/v1/projects/{project_id}/api-keys",
        headers=h,
        json={"name": "sdk-govern", "scopes": ["govern:write"]},
        timeout=30,
    )
    assert kr.status_code == 201, kr.text
    api_key = kr.json()["data"]["full_key"]
    time.sleep(0.2)

    return {
        "base_url": BASE,
        "api_key": api_key,
        "access_token": access,
        "project_id": project_id,
    }


@pytest.mark.integration
def test_govern_report_verify_chain(integration_ctx: dict[str, str]) -> None:
    axiom.init(api_key=integration_ctx["api_key"], base_url=integration_ctx["base_url"])

    g = axiom.govern(
        agent_id="sdk-agent",
        action_type="tool.http.get",
        target="https://api.example.com/r",
        risk="low",
    )
    assert g.verdict in ("allow", "hold", "deny")

    if g.verdict != "allow":
        pytest.skip("Policy did not allow action; cannot test report/verify in this environment")

    rep = axiom.report(
        g.receipt_id,
        outcome={
            "target": "https://api.example.com/r",
            "action_type": "tool.http.get",
            "risk": "low",
        },
    )
    assert rep.status == "sealed"

    v = axiom.verify(g.receipt_id)
    assert v.valid is True
    assert v.checks.get("ed25519") is True

    g1 = axiom.govern(
        agent_id="sdk-agent",
        action_type="tool.http.get",
        target="https://api.example.com/r2",
        risk="low",
        workflow="sdk-chain-wf",
    )
    assert g1.chain_id

    g2 = axiom.govern(
        agent_id="sdk-agent",
        action_type="tool.http.get",
        target="https://api.example.com/r3",
        risk="low",
        chain_id=g1.chain_id,
    )
    assert g2.chain_id == g1.chain_id

    closed = axiom.close_chain(g1.chain_id)
    assert closed.status in ("sealed", "auto_closed")


@pytest.mark.integration
def test_hold_approve_wait_for_decision(integration_ctx: dict[str, str]) -> None:
    base = integration_ctx["base_url"]
    axiom.init(api_key=integration_ctx["api_key"], base_url=base)

    g = axiom.govern(
        agent_id="sdk-agent",
        action_type="tool.email.send",
        target="cfo@company.com",
        risk="high",
        enforce=False,
    )
    if g.verdict != "hold":
        pytest.skip("Policy did not hold high-risk action in this environment")

    h = {"Authorization": f"Bearer {integration_ctx['access_token']}"}
    ap = requests.post(
        f"{base}/v1/governance/receipts/{g.receipt_id}/approve",
        headers=h,
        json={},
        timeout=30,
    )
    assert ap.status_code == 200, ap.text

    polled = axiom.get_receipt(g.receipt_id)
    assert polled.verdict == "allow"

    final = axiom.wait_for_decision(g.receipt_id, poll_interval=0.2, timeout=30.0)
    assert final.verdict == "allow"
