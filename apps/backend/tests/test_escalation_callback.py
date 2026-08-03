"""Inbound n8n callback: HMAC verification + receipt resolution."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from axiom.config import get_settings
from axiom.db import session_scope
from axiom.models.governance import GovernanceReceipt
from axiom.models.project import Project
from axiom.services.escalation.signing import SIGNATURE_HEADER, sign_body
from tests.fixtures.governance import bootstrap_project_with_api_key

CALLBACK = "/webhooks/n8n/escalation-result"
SECRET = "test_callback_secret"


@pytest.fixture
def callback_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("N8N_CALLBACK_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _signed(body: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode("utf-8")
    return raw, {SIGNATURE_HEADER: sign_body(SECRET, raw), "Content-Type": "application/json"}


async def _create_hold(client: AsyncClient) -> str:
    """Drive the govern engine to a 'hold' verdict → a pending receipt."""
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        settings = dict(project.settings)
        settings["governance_policy"] = "starter-safe"
        project.settings = settings
    resp = await client.post(
        "/v1/governance/govern",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"agent_id": "a1", "action_type": "t", "target": "https://x", "risk": "high"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdict"] == "hold"
    return str(resp.json()["receipt_id"])


@pytest.mark.usefixtures("callback_secret")
async def test_callback_approves_and_seals(client: AsyncClient) -> None:
    receipt_id = await _create_hold(client)
    raw, headers = _signed({"receipt_id": receipt_id, "decision": "approved", "reason": "ok"})
    resp = await client.post(CALLBACK, content=raw, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["approval_status"] == "approved"
    async with session_scope() as session:
        receipt = await session.get(GovernanceReceipt, UUID(receipt_id))
        assert receipt is not None
        assert receipt.approval_status == "approved"
        assert receipt.status == "sealed"


@pytest.mark.usefixtures("callback_secret")
async def test_callback_rejects(client: AsyncClient) -> None:
    receipt_id = await _create_hold(client)
    raw, headers = _signed({"receipt_id": receipt_id, "decision": "rejected", "reason": "no"})
    resp = await client.post(CALLBACK, content=raw, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["approval_status"] == "rejected"


@pytest.mark.usefixtures("callback_secret")
async def test_callback_escalated_to_human_leaves_pending(client: AsyncClient) -> None:
    receipt_id = await _create_hold(client)
    raw, headers = _signed({"receipt_id": receipt_id, "decision": "escalated_to_human"})
    resp = await client.post(CALLBACK, content=raw, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["approval_status"] == "pending"


@pytest.mark.usefixtures("callback_secret")
async def test_callback_missing_signature_is_401(client: AsyncClient) -> None:
    raw = json.dumps({"receipt_id": str(uuid4()), "decision": "approved"}).encode("utf-8")
    resp = await client.post(CALLBACK, content=raw, headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


@pytest.mark.usefixtures("callback_secret")
async def test_callback_invalid_signature_is_401(client: AsyncClient) -> None:
    raw = json.dumps({"receipt_id": str(uuid4()), "decision": "approved"}).encode("utf-8")
    resp = await client.post(
        CALLBACK,
        content=raw,
        headers={SIGNATURE_HEADER: "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.usefixtures("callback_secret")
async def test_callback_valid_sig_unknown_receipt_is_404(client: AsyncClient) -> None:
    raw, headers = _signed({"receipt_id": str(uuid4()), "decision": "approved"})
    resp = await client.post(CALLBACK, content=raw, headers=headers)
    assert resp.status_code == 404


async def test_callback_without_configured_secret_is_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("N8N_CALLBACK_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        raw = json.dumps({"receipt_id": str(uuid4()), "decision": "approved"}).encode("utf-8")
        resp = await client.post(
            CALLBACK, content=raw, headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 503
    finally:
        get_settings.cache_clear()
