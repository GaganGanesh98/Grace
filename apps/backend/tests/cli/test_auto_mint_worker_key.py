"""Tests for axiom.cli.automint worker key minting."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import func, select

from axiom.cli.automint import (
    DEV_PROJECT_SLUG,
    DEV_USER_EMAIL,
    WORKER_KEY_NAME,
    ensure_worker_gateway_key,
    rotate_worker_gateway_key,
)
from axiom.config import get_settings
from axiom.db import session_scope
from axiom.models.api_key import ApiKey
from axiom.models.project import Project
from axiom.models.user import User


def _write_minimal_env(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+asyncpg://axiom:axiom_dev_only@127.0.0.1:5433/axiom_test",
                "REDIS_URL=redis://127.0.0.1:6380/1",
                "SECRET_KEY=" + "x" * 64,
                "JWT_SECRET=" + "y" * 32,
                "ENCRYPTION_KEY=" + "z" * 32,
                "",
            ]
        ),
        encoding="utf-8",
    )


@pytest.fixture
def automint_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "backend.env"
    _write_minimal_env(p)
    monkeypatch.setenv("CI", "")
    monkeypatch.setenv("GITHUB_ACTIONS", "")
    monkeypatch.delenv("AXIOM_WORKER_GATEWAY_API_KEY", raising=False)
    get_settings.cache_clear()
    return p


async def test_mint_creates_dev_user_project_and_key(automint_env_path: Path) -> None:
    get_settings.cache_clear()
    await ensure_worker_gateway_key(automint_env_path)
    secret_line = None
    for line in automint_env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("AXIOM_WORKER_GATEWAY_API_KEY="):
            secret_line = line.split("=", 1)[1]
            break
    assert secret_line is not None
    assert secret_line.startswith("axm_live_")
    digest = hashlib.sha256(secret_line.encode("utf-8")).hexdigest()

    async with session_scope() as session:
        user = await session.scalar(select(User).where(User.email == DEV_USER_EMAIL.lower()))
        assert user is not None
        project = await session.scalar(
            select(Project).where(
                Project.slug == DEV_PROJECT_SLUG,
                Project.owner_user_id == user.id,
            )
        )
        assert project is not None
        row = await session.scalar(
            select(ApiKey).where(
                ApiKey.project_id == project.id,
                ApiKey.name == WORKER_KEY_NAME,
                ApiKey.revoked_at.is_(None),
            )
        )
        assert row is not None
        assert row.key_hash == digest


async def test_mint_idempotent_on_existing_valid_key(automint_env_path: Path) -> None:
    get_settings.cache_clear()
    await ensure_worker_gateway_key(automint_env_path)
    await ensure_worker_gateway_key(automint_env_path)

    async with session_scope() as session:
        n = int(
            await session.scalar(
                select(func.count())
                .select_from(ApiKey)
                .where(ApiKey.name == WORKER_KEY_NAME, ApiKey.revoked_at.is_(None))
            )
            or 0
        )
        assert n == 1


async def test_mint_replaces_stale_key(automint_env_path: Path) -> None:
    get_settings.cache_clear()
    await ensure_worker_gateway_key(automint_env_path)
    stale = "axm_live_this_is_a_fake_stale_secret_value_zz"
    text = automint_env_path.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.startswith("AXIOM_WORKER_GATEWAY_API_KEY="):
            lines.append(f"AXIOM_WORKER_GATEWAY_API_KEY={stale}")
        else:
            lines.append(line)
    automint_env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    await ensure_worker_gateway_key(automint_env_path)
    written = None
    for line in automint_env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("AXIOM_WORKER_GATEWAY_API_KEY="):
            written = line.split("=", 1)[1]
            break
    assert written is not None
    assert written != stale
    assert written.startswith("axm_live_")


async def test_rotate_revokes_old_mints_new(automint_env_path: Path) -> None:
    get_settings.cache_clear()
    await ensure_worker_gateway_key(automint_env_path)
    async with session_scope() as session:
        row1 = await session.scalar(select(ApiKey).where(ApiKey.name == WORKER_KEY_NAME))
        assert row1 is not None
        first_id = row1.id
        prefix_1 = row1.key_prefix

    await rotate_worker_gateway_key(automint_env_path)

    async with session_scope() as session:
        old = await session.get(ApiKey, first_id)
        assert old is not None
        assert old.revoked_at is not None
        rows = (
            await session.scalars(
                select(ApiKey).where(
                    ApiKey.name == WORKER_KEY_NAME,
                    ApiKey.revoked_at.is_(None),
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].key_prefix != prefix_1


async def test_ci_skips_mint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "e.env"
    _write_minimal_env(p)
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("AXIOM_WORKER_GATEWAY_API_KEY", raising=False)
    get_settings.cache_clear()
    out = await ensure_worker_gateway_key(p)
    assert out == "skipped_ci"
    assert "AXIOM_WORKER_GATEWAY_API_KEY" not in p.read_text(encoding="utf-8")


async def test_explicit_shell_skips(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "e.env"
    _write_minimal_env(p)
    monkeypatch.setenv("CI", "")
    monkeypatch.setenv("AXIOM_WORKER_GATEWAY_API_KEY", "axm_live_manual_override_value_here_xx")
    get_settings.cache_clear()
    out = await ensure_worker_gateway_key(p)
    assert out == "skipped_explicit"
