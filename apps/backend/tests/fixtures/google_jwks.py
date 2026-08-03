"""Deterministic Google JWKS fixtures for OAuth testing."""

from __future__ import annotations

import base64
import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from pytest_httpx import HTTPXMock

_FIXTURE_KID = "axiom-test-key-1"


def _int_to_b64url(n: int) -> str:
    byte_length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()


@pytest.fixture(scope="session")
def google_rsa_keypair() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    """One RSA keypair for the entire test session (stable kid, unique modulus per run)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": _FIXTURE_KID,
        "use": "sig",
        "alg": "RS256",
        "n": _int_to_b64url(public_numbers.n),
        "e": _int_to_b64url(public_numbers.e),
    }
    return private_key, jwk


@pytest.fixture
def mock_google_jwks(
    httpx_mock: HTTPXMock,
    google_rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> dict[str, Any]:
    """Intercept Google JWKS URL and return the fixture public key."""
    _, jwk = google_rsa_keypair
    jwks = {"keys": [jwk]}
    httpx_mock.add_response(
        url="https://www.googleapis.com/oauth2/v3/certs",
        json=jwks,
        is_reusable=True,
        is_optional=True,
    )
    return jwks


def make_google_id_token(
    private_key: rsa.RSAPrivateKey,
    *,
    sub: str = "1234567890",
    email: str = "user@example.com",
    email_verified: bool = True,
    aud: str = "test-google-client",
    iss: str = "https://accounts.google.com",
    exp_delta_seconds: int = 3600,
    kid: str = _FIXTURE_KID,
    extra_claims: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    algorithm: str = "RS256",
    signing_key: Any = None,
) -> str:
    """Mint a Google-shaped ID token (RS256 by default) signed for verify_google_id_token tests."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + exp_delta_seconds,
    }
    if extra_claims:
        claims.update(extra_claims)
    hdrs = {"kid": kid, **(headers or {})}
    if algorithm == "RS256":
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return jose_jwt.encode(claims, pem.decode(), algorithm="RS256", headers=hdrs)
    key = signing_key if signing_key is not None else "not-the-google-public-key"
    return jose_jwt.encode(claims, key, algorithm=algorithm, headers=hdrs)
