# ───────────────────────────────────────────────────────────────
# Namespace collision guard — backend vs SDK (both named "axiom").
# Proper fix: rename SDK to axiom_sdk in Phase 7.3.
# ───────────────────────────────────────────────────────────────
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_SRC = (Path(__file__).resolve().parent.parent / "src").as_posix()
if _BACKEND_SRC in sys.path:
    sys.path.remove(_BACKEND_SRC)
sys.path.insert(0, _BACKEND_SRC)

for _mod_name in list(sys.modules.keys()):
    if _mod_name == "axiom" or _mod_name.startswith("axiom."):
        _mod = sys.modules[_mod_name]
        _mod_file = getattr(_mod, "__file__", "") or ""
        if "axiom-sdk" in _mod_file:
            del sys.modules[_mod_name]
# ───────────────────────────────────────────────────────────────

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

# Pytest uses a dedicated Postgres DB + Redis logical DB so TRUNCATE fixtures and
# integration tests cannot wipe ./axiom dev data. Override with AXIOM_PYTEST_USE_DEV_DB=1
# only when intentionally debugging against the live dev database.
_use_dev_db = os.environ.get("AXIOM_PYTEST_USE_DEV_DB", "").lower() in ("1", "true", "yes")
if not _use_dev_db:
    # TEST_DATABASE_URL wins (CI sets it). Otherwise default local axiom_test on :5433.
    os.environ["DATABASE_URL"] = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://axiom:axiom_dev_only@127.0.0.1:5433/axiom_test",
    )
    os.environ["REDIS_URL"] = os.environ.get(
        "TEST_REDIS_URL",
        "redis://127.0.0.1:6380/1",
    )
else:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://axiom:axiom_dev_only@127.0.0.1:5433/axiom",
    )
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6380/0")
os.environ.setdefault("SECRET_KEY", "x" * 64)
os.environ.setdefault("JWT_SECRET", "y" * 32)
os.environ.setdefault("ENCRYPTION_KEY", "z" * 32)
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-secret")
os.environ.setdefault("ENVIRONMENT", "development")

from axiom.config import get_settings

get_settings.cache_clear()

from axiom.main import app

pytest_plugins = ("tests.fixtures.google_jwks",)


@pytest.fixture(autouse=True)
async def _reset_redis_between_tests() -> AsyncIterator[None]:
    from axiom.services import redis_client

    await redis_client.close_redis()
    redis_client._redis = None
    redis = redis_client.get_redis()
    await redis.flushdb()
    yield
    await redis.flushdb()
    await redis_client.close_redis()
    redis_client._redis = None


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex}@example.com"


def unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def signup_user(client: AsyncClient, email: str, password: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["data"]


async def login_user(client: AsyncClient, email: str, password: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}
