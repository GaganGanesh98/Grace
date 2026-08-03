"""Regression tests mapped to the Phase 1.5 v1 sin list (see docs/phases/phase-1-5-hardening.md)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from axiom.core.logging import redact_sensitive
from axiom.core.security import (
    UnsafeUrlError,
    compare_digest_str,
    decode_token,
    validate_external_url,
)
from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


@pytest.mark.security
def test_sin01_constant_time_compare_helpers() -> None:
    assert compare_digest_str("a", "b") is False
    assert compare_digest_str("z", "z") is True


@pytest.mark.security
def test_sin02_no_broad_except_policy() -> None:
    from tests.security.test_no_silent_errors import test_no_bare_or_broad_except_outside_main

    test_no_bare_or_broad_except_outside_main()


@pytest.mark.asyncio
@pytest.mark.security
async def test_sin03_no_stack_traces_on_500(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from axiom.services import projects as projects_service

    async def boom(*args: object, **kwargs: object) -> tuple[list[object], int]:
        raise RuntimeError("TRACEBACK_LEAK_MARKER")

    monkeypatch.setattr(projects_service, "list_projects_for_user", boom)
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    response = await client.get("/api/v1/projects", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 500
    assert "traceback" not in response.text.lower()
    assert "traceback_leak_marker" not in response.text.lower()


@pytest.mark.security
def test_sin04_passwords_redacted_in_logs() -> None:
    event = {"password": "X", "token": "Y"}
    out = redact_sensitive(None, None, event)
    assert out["password"] == "[REDACTED]"
    assert out["token"] == "[REDACTED]"


@pytest.mark.asyncio
@pytest.mark.security
async def test_sin05_rate_limit_enforced(client: AsyncClient) -> None:
    last = None
    for i in range(6):
        last = await client.post(
            "/api/v1/auth/login",
            json={"email": f"sin5-{i}@example.com", "password": "nope1a"},
        )
    assert last is not None
    assert last.status_code == 429


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.usefixtures("disable_auth_login_rate_limit")
async def test_sin06_account_lockout(client: AsyncClient) -> None:
    email = unique_email()
    await signup_user(client, email, "password1a")
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "bad1"},
        )
    locked = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password1a"},
    )
    assert locked.status_code == 429


@pytest.mark.asyncio
@pytest.mark.security
async def test_sin07_cors_not_wildcard(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"Origin": "https://evil.com"})
    assert response.headers.get("access-control-allow-origin") != "https://evil.com"


@pytest.mark.asyncio
@pytest.mark.security
async def test_sin08_security_headers_present(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.headers.get("X-Frame-Options") == "DENY"


@pytest.mark.security
def test_sin09_secret_scanning_hooks_checked_in() -> None:
    root = Path(__file__).resolve().parents[4]
    assert (root / ".pre-commit-config.yaml").is_file()


@pytest.mark.asyncio
@pytest.mark.security
async def test_sin10_body_size_cap(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        headers={"content-length": str(2 * 1024 * 1024)},
        content=b"",
    )
    assert response.status_code == 413


@pytest.mark.asyncio
@pytest.mark.security
async def test_sin11_pagination_cap(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    project = await client.post(
        "/api/v1/projects",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "S", "slug": unique_slug("sin11")},
    )
    pid = project.json()["data"]["id"]
    response = await client.get(
        f"/api/v1/projects/{pid}/policies",
        headers=auth_headers(tokens["access_token"]),
        params={"per_page": 500},
    )
    assert response.status_code == 422


@pytest.mark.security
def test_sin12_ssrf_guard() -> None:
    with pytest.raises(UnsafeUrlError):
        validate_external_url("http://192.168.0.1/")


@pytest.mark.security
def test_decode_rejects_none_algorithm() -> None:
    def b64u(obj: dict[str, object]) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    token = ".".join([b64u({"alg": "none", "typ": "JWT"}), b64u({"sub": "1"}), ""])
    with pytest.raises(ValueError, match="Invalid token algorithm"):
        decode_token(token)
