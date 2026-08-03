"""Service-level tests for google_oauth (JWKS + token verification)."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from jose.constants import ALGORITHMS
from jose.utils import calculate_at_hash
from pytest_httpx import HTTPXMock

from axiom.core import errors
from axiom.services import google_oauth
from axiom.services.redis_client import get_redis
from tests.fixtures.google_jwks import make_google_id_token


def _b64url_json(obj: object) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.fixture(autouse=True)
def _reset_google_jwks_cache() -> Iterator[None]:
    google_oauth._jwks_cache["keys"] = []
    google_oauth._jwks_cache["expires"] = 0.0
    yield None
    google_oauth._jwks_cache["keys"] = []
    google_oauth._jwks_cache["expires"] = 0.0


@pytest.mark.asyncio
async def test_verify_google_id_token_happy_path(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv)
    claims = await google_oauth.verify_google_id_token(token)
    assert claims["sub"] == "1234567890"
    assert claims["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_verify_google_id_token_with_at_hash_succeeds_when_access_token_matches(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    """Regression: Google includes ``at_hash``; python-jose requires ``access_token`` for verify."""
    priv, _ = google_rsa_keypair
    access = "fixture-access-token-for-at-hash"
    at_hash = calculate_at_hash(access, ALGORITHMS.HASHES["RS256"])
    token = make_google_id_token(priv, extra_claims={"at_hash": at_hash})
    claims = await google_oauth.verify_google_id_token(token, access_token=access)
    assert claims["sub"] == "1234567890"


@pytest.mark.asyncio
async def test_verify_google_id_token_with_at_hash_rejects_wrong_access_token(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    access = "fixture-access-token-for-at-hash"
    at_hash = calculate_at_hash(access, ALGORITHMS.HASHES["RS256"])
    token = make_google_id_token(priv, extra_claims={"at_hash": at_hash})
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token, access_token="wrong-access-token")


@pytest.mark.asyncio
async def test_verify_google_id_token_wrong_aud(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv, aud="wrong-client")
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_wrong_iss(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv, iss="https://evil.example")
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_expired(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv, exp_delta_seconds=-3600)
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_hs256_rejected(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    token = make_google_id_token(
        priv,
        algorithm="HS256",
        signing_key="symmetric-secret",
        headers={"kid": "axiom-test-key-1"},
    )
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_unknown_kid(
    httpx_mock: HTTPXMock,
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, jwk = google_rsa_keypair
    other_jwk = {**jwk, "kid": "other-kid"}
    httpx_mock.add_response(
        url="https://www.googleapis.com/oauth2/v3/certs",
        json={"keys": [other_jwk]},
        is_reusable=True,
    )
    token = make_google_id_token(priv, kid="axiom-test-key-1")
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_bad_jwks_keys_shape(
    httpx_mock: HTTPXMock,
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    httpx_mock.add_response(
        url="https://www.googleapis.com/oauth2/v3/certs",
        json={"keys": "not-a-list"},
        is_reusable=True,
    )
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv)
    with pytest.raises(errors.InvalidCredentialsError, match="Unexpected JWKS"):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_jwks_unreachable(
    httpx_mock: HTTPXMock,
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    httpx_mock.add_exception(
        httpx.ConnectError("refused"),
        url="https://www.googleapis.com/oauth2/v3/certs",
    )
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv)
    with pytest.raises(httpx.ConnectError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_invalid_header() -> None:
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token("not-a-jwt")


@pytest.mark.asyncio
async def test_verify_google_id_token_missing_kid(
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    now = int(time.time())
    claims = {
        "sub": "1",
        "email": "e@example.com",
        "email_verified": True,
        "aud": "test-google-client",
        "iss": "https://accounts.google.com",
        "iat": now,
        "exp": now + 3600,
    }
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token = jose_jwt.encode(claims, pem.decode(), algorithm="RS256", headers={})
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_email_not_verified(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv, email_verified=False)
    with pytest.raises(errors.InvalidCredentialsError, match="verified"):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_verify_google_id_token_alg_none_rejected(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    _ = google_rsa_keypair
    now = int(time.time())
    payload = {
        "sub": "1",
        "email": "e@example.com",
        "email_verified": True,
        "aud": "test-google-client",
        "iss": "https://accounts.google.com",
        "iat": now,
        "exp": now + 3600,
    }
    token = ".".join(
        [
            _b64url_json({"alg": "none", "kid": "axiom-test-key-1", "typ": "JWT"}),
            _b64url_json(payload),
            "",
        ]
    )
    with pytest.raises(errors.InvalidCredentialsError):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_jwks_cache_avoids_second_http_fetch(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    t1 = make_google_id_token(priv, sub="111")
    t2 = make_google_id_token(priv, sub="222")
    await google_oauth.verify_google_id_token(t1)
    await google_oauth.verify_google_id_token(t2)
    jwks_requests = list(httpx_mock.get_requests(url="https://www.googleapis.com/oauth2/v3/certs"))
    assert len(jwks_requests) == 1


@pytest.mark.asyncio
async def test_exchange_code_rejects_missing_state() -> None:
    with pytest.raises(errors.OAuthStateError):
        await google_oauth.exchange_code(code="x", state=None)


@pytest.mark.asyncio
async def test_exchange_code_rejects_empty_state_string() -> None:
    with pytest.raises(errors.OAuthStateError):
        await google_oauth.exchange_code(code="x", state="")


@pytest.mark.asyncio
async def test_exchange_code_rejects_unknown_state() -> None:
    with pytest.raises(errors.OAuthStateError):
        await google_oauth.exchange_code(code="x", state="not-in-redis")


@pytest.mark.asyncio
async def test_exchange_code_token_endpoint_error(httpx_mock: HTTPXMock) -> None:
    state = "oauth-test-state"
    await get_redis().set(f"oauth_state:{state}", "1", ex=600)
    httpx_mock.add_response(
        method="POST",
        url="https://oauth2.googleapis.com/token",
        status_code=500,
    )
    with pytest.raises(errors.InvalidCredentialsError, match="exchange failed"):
        await google_oauth.exchange_code(code="auth-code", state=state)


@pytest.mark.asyncio
async def test_exchange_code_success_returns_profile(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    id_token = make_google_id_token(priv, sub="google-sub-ok", email="ok@example.com")
    state = "oauth-ok-state"
    await get_redis().set(f"oauth_state:{state}", "1", ex=600)
    httpx_mock.add_response(
        method="POST",
        url="https://oauth2.googleapis.com/token",
        json={"id_token": id_token},
    )
    profile = await google_oauth.exchange_code(code="auth-code", state=state)
    assert profile["sub"] == "google-sub-ok"
    assert profile["email"] == "ok@example.com"


@pytest.mark.asyncio
async def test_exchange_code_rejects_profile_missing_sub(
    httpx_mock: HTTPXMock,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    id_token = make_google_id_token(priv, sub="", email="x@example.com")
    state = "oauth-bad-sub"
    await get_redis().set(f"oauth_state:{state}", "1", ex=600)
    httpx_mock.add_response(
        method="POST",
        url="https://oauth2.googleapis.com/token",
        json={"id_token": id_token},
    )
    with pytest.raises(errors.InvalidCredentialsError, match="required fields"):
        await google_oauth.exchange_code(code="auth-code", state=state)


@pytest.mark.asyncio
async def test_exchange_code_missing_id_token(httpx_mock: HTTPXMock) -> None:
    state = "oauth-test-state-2"
    await get_redis().set(f"oauth_state:{state}", "1", ex=600)
    httpx_mock.add_response(
        method="POST",
        url="https://oauth2.googleapis.com/token",
        json={"access_token": "at"},
    )
    with pytest.raises(errors.InvalidCredentialsError, match="exchange failed"):
        await google_oauth.exchange_code(code="auth-code", state=state)


@pytest.mark.asyncio
async def test_verify_google_id_token_rejects_non_dict_claims(
    monkeypatch: pytest.MonkeyPatch,
    mock_google_jwks: dict[str, Any],
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    priv, _ = google_rsa_keypair
    token = make_google_id_token(priv)

    def _fake_decode(*_a: object, **_k: object) -> list[str]:
        return ["not-a-dict"]

    monkeypatch.setattr(google_oauth.jwt, "decode", _fake_decode)
    with pytest.raises(errors.InvalidCredentialsError, match="Invalid Google identity token"):
        await google_oauth.verify_google_id_token(token)


@pytest.mark.asyncio
async def test_build_authorize_url_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from axiom.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(errors.OAuthConfigurationError, match="GOOGLE_CLIENT_ID"):
            await google_oauth.build_authorize_url()
    finally:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-google-secret")
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_exchange_code_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from axiom.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(errors.OAuthConfigurationError, match="GOOGLE_CLIENT_ID"):
            await google_oauth.exchange_code(code="x", state="any")
    finally:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-google-secret")
        get_settings.cache_clear()
