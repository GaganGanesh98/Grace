"""Provider Fabric — registry, protocol handlers, gateway, vault integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from axiom.config import get_settings
from axiom.db import session_scope
from axiom.gateway.app import app
from axiom.gateway.protocol_handlers import (
    build_upstream_url,
    dispatch_to_provider,
    merge_forward_headers,
    prepare_upstream_request,
    proxy_anthropic_messages,
    proxy_google_gemini,
    proxy_openai_compatible,
)
from axiom.gateway.provider_registry import (
    PROVIDERS,
    ProtocolShape,
    detect_provider_from_key,
    get_all_provider_names,
    get_provider_spec,
    get_providers_by_protocol,
)
from axiom.models.vault import VaultKey
from axiom.services import vault as vault_service
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key

# --- Registry tests ---


def test_detect_groq_key() -> None:
    assert detect_provider_from_key("gsk_abc123") == "groq"


def test_detect_openai_proj_key() -> None:
    assert detect_provider_from_key("sk-proj-abc123") == "openai"


def test_detect_openai_legacy_key() -> None:
    assert detect_provider_from_key("sk-abc123") == "openai"


def test_detect_anthropic_key() -> None:
    assert detect_provider_from_key("sk-ant-api03-abc123") == "anthropic"


def test_detect_xai_key() -> None:
    assert detect_provider_from_key("xai-abc123") == "xai"


def test_detect_google_key() -> None:
    assert detect_provider_from_key("AIzaSy-abc123") == "google"


def test_detect_perplexity_key() -> None:
    assert detect_provider_from_key("pplx-abc123") == "perplexity"


def test_detect_openrouter_key() -> None:
    assert detect_provider_from_key("sk-or-abc123") == "openrouter"


def test_detect_fireworks_key() -> None:
    assert detect_provider_from_key("fp_abc123") == "fireworks"


def test_detect_cerebras_key() -> None:
    assert detect_provider_from_key("csk-abc123") == "cerebras"


def test_detect_unknown_key() -> None:
    assert detect_provider_from_key("xyz_unknown") is None


def test_prefix_ordering_anthropic() -> None:
    assert detect_provider_from_key("sk-ant-api03-xxx") == "anthropic"


def test_prefix_ordering_proj() -> None:
    assert detect_provider_from_key("sk-proj-xxx") == "openai"


def test_prefix_ordering_openrouter() -> None:
    assert detect_provider_from_key("sk-or-xxx") == "openrouter"


def test_get_provider_spec_exists() -> None:
    spec = get_provider_spec("groq")
    assert spec is not None
    assert spec.name == "groq"


def test_get_provider_spec_missing() -> None:
    assert get_provider_spec("fakeprovider") is None


def test_all_providers_have_base_url() -> None:
    for spec in PROVIDERS.values():
        assert spec.base_url.strip()


def test_all_providers_have_protocol() -> None:
    for spec in PROVIDERS.values():
        assert spec.protocol in ProtocolShape


def test_registry_immutable() -> None:
    spec = get_provider_spec("groq")
    assert spec is not None
    with pytest.raises(AttributeError):
        spec.base_url = "x"  # type: ignore[misc]


def test_get_providers_by_protocol_openai() -> None:
    groq_specs = get_providers_by_protocol(ProtocolShape.OPENAI_COMPATIBLE)
    assert any(s.name == "groq" for s in groq_specs)


def test_get_all_provider_names_lists_registry_keys() -> None:
    names = get_all_provider_names()
    assert "groq" in names
    assert "openai" in names
    assert len(names) == len(PROVIDERS)


# --- Protocol handler tests ---


@pytest.mark.asyncio
async def test_openai_handler_constructs_correct_url() -> None:
    spec = get_provider_spec("groq")
    assert spec is not None
    captured: dict[str, str] = {}

    async def fake_post(url: str, **_k: object) -> httpx.Response:
        captured["url"] = url
        return httpx.Response(200, json={"ok": True})

    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=fake_post)
    await proxy_openai_compatible(
        spec,
        "k",
        b"{}",
        "chat/completions",
        client,  # type: ignore[arg-type]
    )
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"


@pytest.mark.asyncio
async def test_openai_handler_uses_bearer_auth() -> None:
    spec = get_provider_spec("groq")
    assert spec is not None
    captured: dict[str, str] = {}

    async def fake_post(_url: str, **_k: object) -> httpx.Response:
        hdrs = _k.get("headers") or {}
        captured["authorization"] = str(hdrs.get("Authorization", ""))
        return httpx.Response(200, json={"ok": True})

    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=fake_post)
    await proxy_openai_compatible(
        spec,
        "secret-token",
        b"{}",
        "chat/completions",
        client,  # type: ignore[arg-type]
    )
    assert captured["authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_anthropic_handler_uses_x_api_key() -> None:
    spec = get_provider_spec("anthropic")
    assert spec is not None
    captured: dict[str, str] = {}

    async def fake_post(_url: str, **_k: object) -> httpx.Response:
        hdrs = _k.get("headers") or {}
        captured["x-api-key"] = str(hdrs.get("x-api-key", ""))
        captured["authorization"] = str(hdrs.get("Authorization", ""))
        return httpx.Response(200, json={"ok": True})

    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=fake_post)
    await proxy_anthropic_messages(
        spec,
        "ant-secret",
        b"{}",
        "messages",
        client,  # type: ignore[arg-type]
    )
    assert captured["x-api-key"] == "ant-secret"
    assert captured["authorization"] == ""


@pytest.mark.asyncio
async def test_anthropic_handler_includes_version_header() -> None:
    spec = get_provider_spec("anthropic")
    assert spec is not None
    captured: dict[str, str] = {}

    async def fake_post(_url: str, **_k: object) -> httpx.Response:
        hdrs = _k.get("headers") or {}
        captured["anthropic-version"] = str(hdrs.get("anthropic-version", ""))
        return httpx.Response(200, json={"ok": True})

    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=fake_post)
    await proxy_anthropic_messages(
        spec,
        "ant-secret",
        b"{}",
        "messages",
        client,  # type: ignore[arg-type]
    )
    assert captured["anthropic-version"] == "2023-06-01"


@pytest.mark.asyncio
async def test_google_handler_uses_query_param_auth() -> None:
    spec = get_provider_spec("google")
    assert spec is not None
    captured: dict[str, str] = {}

    async def fake_post(url: str, **_k: object) -> httpx.Response:
        captured["url"] = url
        hdrs = _k.get("headers") or {}
        captured["authorization"] = str(hdrs.get("Authorization", ""))
        return httpx.Response(200, json={"ok": True})

    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=fake_post)
    await proxy_google_gemini(
        spec,
        "AIza-google-key",
        b"{}",
        "models/gemini-pro:generateContent",
        client,  # type: ignore[arg-type]
    )
    assert "key=AIza-google-key" in captured["url"]
    assert captured["authorization"] == ""


@pytest.mark.asyncio
async def test_dispatch_routes_groq_to_openai_handler() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    await dispatch_to_provider("groq", "k", b"{}", "chat/completions", client)  # type: ignore[arg-type]
    assert client.post.await_count == 1
    call_kw = client.post.call_args
    assert "api.groq.com" in str(call_kw[0][0])


@pytest.mark.asyncio
async def test_dispatch_routes_anthropic_correctly() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    await dispatch_to_provider("anthropic", "k", b"{}", "messages", client)  # type: ignore[arg-type]
    assert client.post.await_count == 1
    assert "api.anthropic.com" in str(client.post.call_args[0][0])


@pytest.mark.asyncio
async def test_dispatch_routes_google_correctly() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    await dispatch_to_provider("google", "k", b"{}", "models/x:generateContent", client)  # type: ignore[arg-type]
    assert client.post.await_count == 1
    assert "generativelanguage.googleapis.com" in str(client.post.call_args[0][0])


@pytest.mark.asyncio
async def test_dispatch_unknown_provider_raises() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    with pytest.raises(ValueError, match="Unknown provider"):
        await dispatch_to_provider("fake", "k", b"{}", "x", client)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_prepare_upstream_google_no_bearer_in_headers() -> None:
    spec = get_provider_spec("google")
    assert spec is not None
    url = build_upstream_url(spec, "models/m:generateContent")
    h, u = prepare_upstream_request(spec, "KEY", url, {"Content-Type": "application/json"})
    assert "Authorization" not in h
    assert "key=KEY" in u


# --- Integration tests ---


@pytest.fixture
async def gateway_client() -> object:
    get_settings.cache_clear()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://gateway.test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_gateway_groq_route_returns_200(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={"raw_key": "gsk_11111111111111111111111111111111", "name": "groq-key"},
    )

    async def fake_proxy(*_a: object, **_k: object) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)
    r = await gateway_client.post(
        "/v1/groq/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "llama", "messages": []},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_gateway_anthropic_route_returns_200(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={
            "raw_key": "sk-ant-api03-11111111111111111111111111111111",
            "name": "ant",
        },
    )

    async def fake_proxy(*_a: object, **_k: object) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)
    r = await gateway_client.post(
        "/v1/anthropic/messages",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "claude", "messages": []},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_gateway_unknown_provider_returns_404(
    client: AsyncClient,
    gateway_client: AsyncClient,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await gateway_client.post(
        "/v1/fakeprovider/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "x"},
    )
    assert r.status_code == 404
    body = r.json()
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        assert "fakeprovider" in detail.get("message", "")


@pytest.mark.asyncio
async def test_gateway_preserves_governance_receipt(
    client: AsyncClient,
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from axiom.services.governance.policy import PolicyResult

    fx = await bootstrap_project_with_api_key(client)
    await client.post(
        "/api/v1/vault",
        headers=auth_headers(fx["user_access"]),
        json={"raw_key": "gsk_22222222222222222222222222222222", "name": "g2"},
    )

    async def fake_proxy(*_a: object, **_k: object) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("axiom.gateway.app.proxy_request", fake_proxy)

    def deny(_i: object, _c: object) -> PolicyResult:
        return PolicyResult(
            verdict="deny",
            reason="no",
            policy_version="p-v1",
            rules_evaluated=[],
            risk_assessed="low",
        )

    monkeypatch.setattr("axiom.gateway.pipeline.evaluate_policy", deny)
    r = await gateway_client.post(
        "/v1/groq/chat/completions",
        headers={"Authorization": f"Bearer {fx['api_key_full']}"},
        json={"model": "x"},
    )
    assert r.status_code == 403
    assert r.json().get("receipt_id")


@pytest.mark.asyncio
async def test_vault_uses_registry_for_detection() -> None:
    from axiom.models.member import MemberRole, ProjectMember
    from axiom.models.project import Project
    from axiom.services import auth as auth_service

    async with session_scope() as session:
        user, _, _ = await auth_service.signup(
            session, email=f"pf-{uuid4().hex}@example.com", password="password1a", full_name="T"
        )
        project = await session.scalar(select(Project).where(Project.owner_user_id == user.id))
        if project is None:
            slug = f"v-{uuid4().hex}"
            project = Project(slug=slug, name="T", description=None, owner_user_id=user.id)
            session.add(project)
            await session.flush()
            session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    role=MemberRole.OWNER.value,
                    invited_by_user_id=None,
                )
            )
            await session.flush()
        row, detected = await vault_service.store_key(
            session, user.id, None, "G", "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        )
        await session.commit()
        assert detected == "groq"
        vk = await session.get(VaultKey, row.id)
        assert vk is not None
        assert vk.service == "groq"


def test_merge_forward_headers_strips_axiom_and_auth() -> None:
    h = merge_forward_headers(
        {
            "Authorization": "Bearer user",
            "X-Axiom-Agent-Id": "a1",
            "Content-Type": "application/json",
        }
    )
    assert "Authorization" not in h
    assert "X-Axiom-Agent-Id" not in h
    assert h.get("Content-Type") == "application/json"
