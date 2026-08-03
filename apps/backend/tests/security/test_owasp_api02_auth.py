import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from axiom.config import get_settings
from axiom.core.security import decode_token
from tests.conftest import auth_headers, signup_user, unique_email


def _b64url_json(obj: dict[str, object]) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.mark.asyncio
@pytest.mark.security
async def test_me_without_authorization_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.security
def test_decode_rejects_alg_none() -> None:
    token = ".".join(
        [
            _b64url_json({"alg": "none", "typ": "JWT"}),
            _b64url_json({"sub": "1"}),
            "",
        ]
    )
    with pytest.raises(ValueError, match="Invalid token algorithm"):
        decode_token(token)


@pytest.mark.security
def test_decode_rejects_wrong_secret() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    bad = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "type": "access",
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        "wrong-secret-not-the-real-one-xxxxxxxx",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(ValueError):
        decode_token(bad)


@pytest.mark.asyncio
@pytest.mark.security
async def test_me_rejects_tampered_token(client: AsyncClient) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")
    token = tokens["access_token"]
    tampered = token[:-4] + "xxxx"
    response = await client.get("/api/v1/auth/me", headers=auth_headers(tampered))
    assert response.status_code == 401
