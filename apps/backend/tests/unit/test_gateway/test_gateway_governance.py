"""Gateway governance integration (policy + receipts)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from axiom.db import session_scope
from axiom.models.governance import GovernanceChain, GovernanceReceipt
from axiom.services.governance.policy import PolicyResult
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.mark.asyncio
async def test_denied_request_returns_403_with_receipt(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)

    def deny(_i, _c):
        return PolicyResult(
            verdict="deny",
            reason="no",
            policy_version="p-v1",
            rules_evaluated=[],
            risk_assessed="low",
        )

    monkeypatch.setattr("axiom.gateway.pipeline.evaluate_policy", deny)
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4"},
    )
    assert r.status_code == 403
    body = r.json()
    assert body.get("error") == "governance_denied"
    assert body.get("receipt_id")


@pytest.mark.asyncio
async def test_held_request_returns_202_with_receipt(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)

    def hold(_i, _c):
        return PolicyResult(
            verdict="hold",
            reason="wait",
            policy_version="p-v1",
            rules_evaluated=[],
            risk_assessed="high",
        )

    monkeypatch.setattr("axiom.gateway.pipeline.evaluate_policy", hold)
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4"},
    )
    assert r.status_code == 202
    assert r.json().get("status") == "held"


@pytest.mark.asyncio
async def test_receipt_id_in_response_header(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)

    def deny(_i, _c):
        return PolicyResult(
            verdict="deny",
            reason="no",
            policy_version="p-v1",
            rules_evaluated=[],
            risk_assessed="low",
        )

    monkeypatch.setattr("axiom.gateway.pipeline.evaluate_policy", deny)
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4"},
    )
    assert r.headers.get("x-axiom-receipt-id")


@pytest.mark.asyncio
async def test_receipt_signed_for_every_request(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)

    def deny(_i, _c):
        return PolicyResult(
            verdict="deny",
            reason="no",
            policy_version="p-v1",
            rules_evaluated=[],
            risk_assessed="low",
        )

    monkeypatch.setattr("axiom.gateway.pipeline.evaluate_policy", deny)
    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4"},
    )
    rid = r.json()["receipt_id"]
    async with session_scope() as db:
        row = await db.get(GovernanceReceipt, UUID(rid))
        assert row is not None
        assert row.status == "sealed"
        assert row.ed25519_sig is not None


@pytest.mark.asyncio
async def test_denied_request_never_reaches_provider(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)

    def deny(_i, _c):
        return PolicyResult(
            verdict="deny",
            reason="no",
            policy_version="p-v1",
            rules_evaluated=[],
            risk_assessed="low",
        )

    monkeypatch.setattr("axiom.gateway.pipeline.evaluate_policy", deny)
    track = AsyncMock(side_effect=AssertionError("upstream should not be called"))
    monkeypatch.setattr("axiom.gateway.app.proxy_request", track)
    await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4"},
    )
    track.assert_not_called()


@pytest.mark.asyncio
async def test_allowed_request_proxied_to_provider(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={
            "raw_key": "sk-proj-11111111111111111111111111111111",
            "name": "P",
        },
    )

    async def fake_proxy(*_a, **_k):
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4", "messages": []},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vault_key_injected_into_outbound_request(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={
            "raw_key": "sk-proj-22222222222222222222222222222222",
            "name": "Q",
        },
    )

    captured: dict[str, str] = {}

    async def fake_proxy(_client, _method, _url, headers, _body, *, timeout=120.0):
        captured["auth"] = headers.get("Authorization") or headers.get("authorization", "")
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4", "messages": []},
    )
    assert "Bearer sk-proj-" in captured.get("auth", "")


@pytest.mark.asyncio
async def test_governance_chain_created_per_workflow(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={
            "raw_key": "sk-proj-33333333333333333333333333333333",
            "name": "R",
        },
    )
    async def fake_proxy(*_a, **_k):
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4", "messages": []},
    )
    async with session_scope() as db:
        rows = list(
            await db.scalars(
                select(GovernanceChain).where(GovernanceChain.project_id == UUID(fx["project_id"]))
            )
        )
        assert any(r.workflow_name == "gateway" for r in rows)
