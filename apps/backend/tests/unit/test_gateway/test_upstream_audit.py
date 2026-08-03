"""Per-call forensic audit fields attached to governance receipts."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

import httpx
import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.gateway.upstream_audit import (
    parse_model_from_request,
    parse_token_usage,
    sha256_hex,
)
from axiom.models.governance import GovernanceReceipt
from axiom.workers.react_loop import _post_gateway_completion
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key


def _audit_from_receipt(receipt: GovernanceReceipt) -> dict:
    assert receipt.execution_data is not None, "receipt has no execution_data"
    audit = receipt.execution_data.get("upstream_audit")
    assert audit is not None, "execution_data missing upstream_audit"
    return audit


async def _seed_openai_project(client: AsyncClient) -> dict:
    fx = await bootstrap_project_with_api_key(client)
    await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={
            "raw_key": "sk-proj-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "name": "k",
        },
    )
    return fx


@pytest.mark.asyncio
async def test_receipt_includes_request_hash(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await _seed_openai_project(client)
    # Send raw bytes so the hash is deterministic regardless of httpx serialization.
    request_body = b'{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'

    async def fake_proxy(*_a, **_k) -> httpx.Response:
        return httpx.Response(200, json={"id": "resp"})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={
            "Authorization": f"Bearer {fx['api_key_full']}",
            "Content-Type": "application/json",
        },
        content=request_body,
    )
    assert r.status_code == 200
    rid = UUID(r.headers["x-axiom-receipt-id"])

    async with session_scope() as db:
        row = await db.get(GovernanceReceipt, rid)
        assert row is not None
        audit = _audit_from_receipt(row)

    assert audit["request_hash"] == sha256_hex(request_body)
    assert len(audit["request_hash"]) == 64


@pytest.mark.asyncio
async def test_receipt_includes_response_hash(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await _seed_openai_project(client)
    response_body = b'{"id":"chatcmpl-xyz","object":"chat.completion"}'

    async def fake_proxy(*_a, **_k) -> httpx.Response:
        return httpx.Response(200, content=response_body)

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4o"},
    )
    assert r.status_code == 200
    rid = UUID(r.headers["x-axiom-receipt-id"])

    async with session_scope() as db:
        row = await db.get(GovernanceReceipt, rid)
        assert row is not None
        audit = _audit_from_receipt(row)

    assert audit["response_hash"] == hashlib.sha256(response_body).hexdigest()


@pytest.mark.asyncio
async def test_receipt_includes_token_usage(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await _seed_openai_project(client)

    async def fake_proxy(*_a, **_k) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "r",
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 34,
                    "total_tokens": 46,
                },
            },
        )

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4o"},
    )
    assert r.status_code == 200
    rid = UUID(r.headers["x-axiom-receipt-id"])

    async with session_scope() as db:
        row = await db.get(GovernanceReceipt, rid)
        assert row is not None
        audit = _audit_from_receipt(row)

    assert audit["token_usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 34,
        "total_tokens": 46,
    }
    assert audit["upstream_model"] == "gpt-4o"
    assert audit["upstream_provider"] == "openai"
    assert audit["upstream_status"] == 200
    assert audit["vault_key_id"]  # non-empty UUID string
    UUID(audit["vault_key_id"])  # parseable


@pytest.mark.asyncio
async def test_receipt_includes_upstream_latency(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await _seed_openai_project(client)

    async def fake_proxy(*_a, **_k) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    r = await gateway_client.post(
        "/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "gpt-4o"},
    )
    assert r.status_code == 200
    rid = UUID(r.headers["x-axiom-receipt-id"])

    async with session_scope() as db:
        row = await db.get(GovernanceReceipt, rid)
        assert row is not None
        audit = _audit_from_receipt(row)

    assert isinstance(audit["upstream_latency_ms"], int)
    assert audit["upstream_latency_ms"] >= 0


@pytest.mark.asyncio
async def test_worker_gateway_path_sends_model_and_single_content_type_to_provider(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await _seed_openai_project(client)
    captured: dict[str, object] = {}

    async def fake_proxy(
        _client: httpx.AsyncClient,
        _method: str,
        _url: str,
        headers: dict[str, str],
        body: bytes | None,
        *,
        timeout: float,
    ) -> httpx.Response:
        captured["headers"] = headers
        captured["body"] = body
        captured["timeout"] = timeout
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Final Answer: hello"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            },
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    data, receipt_id = await _post_gateway_completion(
        httpx_client=gateway_client,
        gateway_api_key=fx["api_key_full"],
        provider="openai",
        model="gpt-4o",
        messages=[{"role": "user", "content": "Say hello in one short sentence"}],
        x_axiom_agent_id="00000000-0000-0000-0000-000000000000",
    )

    body = captured["body"]
    assert isinstance(body, bytes)
    parsed_body = json.loads(body)
    assert parsed_body["model"] == "gpt-4o"
    assert data["usage"]["total_tokens"] == 5
    assert receipt_id is not None

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert sum(1 for key in headers if key.lower() == "content-type") == 1
    assert (
        headers.get("content-type") == "application/json"
        or headers.get("Content-Type") == "application/json"
    )


# --- Parser unit tests (no HTTP) ---


def test_parse_token_usage_openai_shape() -> None:
    body = json.dumps({"usage": {"prompt_tokens": 1, "completion_tokens": 2}}).encode()
    assert parse_token_usage(body) == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
    }


def test_parse_token_usage_anthropic_shape() -> None:
    body = json.dumps({"usage": {"input_tokens": 5, "output_tokens": 7}}).encode()
    assert parse_token_usage(body) == {
        "prompt_tokens": 5,
        "completion_tokens": 7,
        "total_tokens": 12,
    }


def test_parse_token_usage_missing() -> None:
    assert parse_token_usage(b'{"id":"r"}') is None


def test_parse_token_usage_unparseable() -> None:
    assert parse_token_usage(b"not json") is None
    assert parse_token_usage(None) is None


def test_parse_model_from_request() -> None:
    assert parse_model_from_request(b'{"model": "gpt-4"}') == "gpt-4"
    assert parse_model_from_request(b'{}') is None
    assert parse_model_from_request(b"garbage") is None
