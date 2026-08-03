"""Outbound webhook client (retry/backoff) + HMAC signing unit tests. No DB."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from axiom.services.escalation.signing import sign_body, verify_signature
from axiom.services.escalation.webhook_client import EscalationDeliveryError, post_with_retry

URL = "https://n8n.test/webhook/axiom-escalation"


async def test_success_first_try(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=200, json={"ok": True})
    response = await post_with_retry(URL, content=b"{}", headers={}, base_delay=0.0)
    assert response.status_code == 200
    assert len(httpx_mock.get_requests()) == 1


async def test_retries_5xx_then_succeeds(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=503)
    httpx_mock.add_response(url=URL, status_code=502)
    httpx_mock.add_response(url=URL, status_code=200)
    response = await post_with_retry(URL, content=b"{}", headers={}, base_delay=0.0)
    assert response.status_code == 200
    assert len(httpx_mock.get_requests()) == 3


async def test_gives_up_after_max_attempts(httpx_mock: HTTPXMock) -> None:
    for _ in range(3):
        httpx_mock.add_response(url=URL, status_code=500)
    with pytest.raises(EscalationDeliveryError):
        await post_with_retry(URL, content=b"{}", headers={}, max_attempts=3, base_delay=0.0)
    assert len(httpx_mock.get_requests()) == 3


async def test_does_not_retry_4xx(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=400)
    response = await post_with_retry(URL, content=b"{}", headers={}, base_delay=0.0)
    assert response.status_code == 400
    assert len(httpx_mock.get_requests()) == 1


async def test_retries_network_error_then_succeeds(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("refused"), url=URL)
    httpx_mock.add_response(url=URL, status_code=200)
    response = await post_with_retry(URL, content=b"{}", headers={}, base_delay=0.0)
    assert response.status_code == 200
    assert len(httpx_mock.get_requests()) == 2


def test_sign_and_verify_roundtrip() -> None:
    body = b'{"receipt_id":"x","decision":"approved"}'
    signature = sign_body("shhh", body)
    assert signature.startswith("sha256=")
    assert verify_signature("shhh", body, signature) is True


def test_verify_rejects_tampered_or_missing() -> None:
    body = b'{"a":1}'
    good = sign_body("shhh", body)
    assert verify_signature("shhh", body, None) is False
    assert verify_signature("shhh", body, "sha256=deadbeef") is False
    assert verify_signature("shhh", b'{"a":2}', good) is False  # body tampered
    assert verify_signature("wrong-secret", body, good) is False  # wrong secret
