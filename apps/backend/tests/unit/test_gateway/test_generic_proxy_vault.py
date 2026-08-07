"""Vault credential injection on the generic proxy (/v1/proxy/{target}).

The generic proxy forwards to arbitrary URLs, so credential handling is
deliberately conservative: nothing is injected unless the caller names a vault
key explicitly via ``X-Axiom-Vault-Key``, the target survived the SSRF guard,
and governance returned allow.

Targets are IP literals so ``assert_public_http_url``'s ``getaddrinfo`` call
resolves without DNS, keeping these tests offline-safe. 1.1.1.1 is public;
127.0.0.1 is loopback and must be refused.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.governance import GovernanceReceipt
from axiom.services.governance.policy import PolicyResult
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key

PUBLIC_TARGET = "1.1.1.1/api"
LOOPBACK_TARGET = "127.0.0.1/api"
VAULT_KEY_NAME = "my-webhook-token"
VAULT_KEY_VALUE = "zz-generic-proxy-secret-0123456789"


async def _add_vault_key(
    client: AsyncClient, fx: dict[str, str], *, name: str, raw_key: str
) -> None:
    r = await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={"raw_key": raw_key, "name": name},
    )
    assert r.status_code in (200, 201), r.text


def _capture_proxy(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Intercept the outbound call and record what would have been sent."""
    seen: dict[str, Any] = {"called": False}

    async def fake_proxy(
        _client: Any,
        method: str,
        url: str,
        headers: dict[str, str],
        _body: bytes | None,
        *,
        timeout: float | None = None,
    ) -> httpx.Response:
        seen["called"] = True
        seen["method"] = method
        seen["url"] = url
        seen["headers"] = headers
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)
    return seen


def _force_verdict(monkeypatch: pytest.MonkeyPatch, verdict: str) -> None:
    def result(_i: Any, _c: Any) -> PolicyResult:
        return PolicyResult(
            verdict=verdict,
            reason="test",
            policy_version="p-v1",
            rules_evaluated=[],
            risk_assessed="low",
        )

    monkeypatch.setattr("axiom.gateway.pipeline.evaluate_policy", result)


def _auth(fx: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {fx['api_key_full']}"}


@pytest.mark.asyncio
async def test_no_header_means_no_injection_and_no_authorization_passthrough(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default behaviour is unchanged: strip Authorization, inject nothing."""
    fx = await bootstrap_project_with_api_key(client)
    await _add_vault_key(client, fx, name=VAULT_KEY_NAME, raw_key=VAULT_KEY_VALUE)
    seen = _capture_proxy(monkeypatch)

    r = await gateway_client.post(f"/v1/proxy/{PUBLIC_TARGET}", headers=_auth(fx), json={"a": 1})

    assert r.status_code == 200, r.text
    assert seen["called"] is True
    out = {k.lower(): v for k, v in seen["headers"].items()}
    # The caller's Axiom API key must never reach the upstream target.
    assert "authorization" not in out
    assert fx["api_key_full"] not in str(seen["headers"])


@pytest.mark.asyncio
async def test_credential_injected_on_allow(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _add_vault_key(client, fx, name=VAULT_KEY_NAME, raw_key=VAULT_KEY_VALUE)
    seen = _capture_proxy(monkeypatch)

    r = await gateway_client.post(
        f"/v1/proxy/{PUBLIC_TARGET}",
        headers={**_auth(fx), "X-Axiom-Vault-Key": VAULT_KEY_NAME},
        json={"a": 1},
    )

    assert r.status_code == 200, r.text
    out = {k.lower(): v for k, v in seen["headers"].items()}
    assert out.get("authorization") == f"Bearer {VAULT_KEY_VALUE}"
    # The header naming the key is internal and must not be forwarded upstream.
    assert "x-axiom-vault-key" not in out


@pytest.mark.asyncio
async def test_no_injection_on_deny(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _add_vault_key(client, fx, name=VAULT_KEY_NAME, raw_key=VAULT_KEY_VALUE)
    seen = _capture_proxy(monkeypatch)
    _force_verdict(monkeypatch, "deny")

    r = await gateway_client.post(
        f"/v1/proxy/{PUBLIC_TARGET}",
        headers={**_auth(fx), "X-Axiom-Vault-Key": VAULT_KEY_NAME},
        json={"a": 1},
    )

    assert r.status_code == 403
    assert r.json().get("error") == "governance_denied"
    assert seen["called"] is False, "denied request must never reach the upstream"


@pytest.mark.asyncio
async def test_no_injection_on_hold(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _add_vault_key(client, fx, name=VAULT_KEY_NAME, raw_key=VAULT_KEY_VALUE)
    seen = _capture_proxy(monkeypatch)
    _force_verdict(monkeypatch, "hold")

    r = await gateway_client.post(
        f"/v1/proxy/{PUBLIC_TARGET}",
        headers={**_auth(fx), "X-Axiom-Vault-Key": VAULT_KEY_NAME},
        json={"a": 1},
    )

    assert r.status_code == 202
    assert r.json().get("status") == "held"
    assert seen["called"] is False, "held request must never reach the upstream"


@pytest.mark.asyncio
async def test_ssrf_target_rejected_before_any_vault_access(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocked target must short-circuit before the vault is ever read."""
    fx = await bootstrap_project_with_api_key(client)
    await _add_vault_key(client, fx, name=VAULT_KEY_NAME, raw_key=VAULT_KEY_VALUE)
    seen = _capture_proxy(monkeypatch)

    vault_reads: list[str] = []
    real_lookup = __import__(
        "axiom.services.vault", fromlist=["get_key_and_id_by_name"]
    ).get_key_and_id_by_name

    async def spy(db: Any, user_id: UUID, name: str) -> Any:
        vault_reads.append(name)
        return await real_lookup(db, user_id, name)

    monkeypatch.setattr("axiom.services.vault.get_key_and_id_by_name", spy)

    r = await gateway_client.post(
        f"/v1/proxy/{LOOPBACK_TARGET}",
        headers={**_auth(fx), "X-Axiom-Vault-Key": VAULT_KEY_NAME},
        json={"a": 1},
    )

    assert r.status_code == 403
    assert vault_reads == [], "SSRF-blocked target must not trigger a vault read"
    assert seen["called"] is False


@pytest.mark.asyncio
async def test_cross_project_key_resolves_to_not_found(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key owned by another tenant is not-found, never forbidden."""
    owner = await bootstrap_project_with_api_key(client)
    other = await bootstrap_project_with_api_key(client)
    await _add_vault_key(client, owner, name=VAULT_KEY_NAME, raw_key=VAULT_KEY_VALUE)
    seen = _capture_proxy(monkeypatch)

    r = await gateway_client.post(
        f"/v1/proxy/{PUBLIC_TARGET}",
        headers={**_auth(other), "X-Axiom-Vault-Key": VAULT_KEY_NAME},
        json={"a": 1},
    )

    assert r.status_code == 404, r.text
    assert r.json().get("error") == "vault_key_not_found"
    assert seen["called"] is False, "unresolved credential must not reach the upstream"

    # Governance had already allowed and opened a receipt before the credential
    # failed to resolve. That receipt must be sealed, not left dangling in the
    # pending state where it would never reach the Merkle log.
    receipt_id = r.headers.get("X-Axiom-Receipt-Id")
    assert receipt_id
    async with session_scope() as db:
        receipt = await db.get(GovernanceReceipt, UUID(receipt_id))
        assert receipt is not None
        assert receipt.execution_data is not None, "receipt left unsealed after vault miss"


@pytest.mark.asyncio
async def test_receipt_records_vault_key_id(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _add_vault_key(client, fx, name=VAULT_KEY_NAME, raw_key=VAULT_KEY_VALUE)
    _capture_proxy(monkeypatch)

    r = await gateway_client.post(
        f"/v1/proxy/{PUBLIC_TARGET}",
        headers={**_auth(fx), "X-Axiom-Vault-Key": VAULT_KEY_NAME},
        json={"a": 1},
    )
    assert r.status_code == 200, r.text
    receipt_id = r.headers.get("X-Axiom-Receipt-Id")
    assert receipt_id

    async with session_scope() as db:
        receipt = await db.get(GovernanceReceipt, UUID(receipt_id))
        assert receipt is not None
        assert receipt.execution_data is not None
        recorded = receipt.execution_data.get("vault_key_id")

    assert recorded, "receipt must record which vault key was used"
    # It records the key's id, never the secret itself.
    assert recorded != VAULT_KEY_VALUE
    assert VAULT_KEY_VALUE not in str(receipt.execution_data)


@pytest.mark.asyncio
async def test_receipt_has_no_vault_key_id_when_none_requested(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    _capture_proxy(monkeypatch)

    r = await gateway_client.post(f"/v1/proxy/{PUBLIC_TARGET}", headers=_auth(fx), json={"a": 1})
    assert r.status_code == 200, r.text
    receipt_id = r.headers.get("X-Axiom-Receipt-Id")
    assert receipt_id

    async with session_scope() as db:
        receipt = await db.get(GovernanceReceipt, UUID(receipt_id))
        assert receipt is not None
        assert receipt.execution_data is not None
        assert receipt.execution_data.get("vault_key_id") is None
