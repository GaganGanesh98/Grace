"""`axiom keys` — status, migrate-vault, rotate, verify (Phase 8.2 Part 4)."""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from axiom.cli import keys as keys_cli
from axiom.db import session_scope
from axiom.models.vault import VaultKey
from axiom.services.crypto import envelope, kek_registry
from axiom.services.crypto import vault as aes_vault
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key

RAW_KEY = "sk-proj-cccccccccccccccccccccccccccccccc"


@pytest.fixture(autouse=True)
async def _isolate_vault_table() -> AsyncIterator[None]:
    async with session_scope() as session:
        # DELETE, not TRUNCATE: TRUNCATE takes ACCESS EXCLUSIVE and deadlocks
        # against any other pytest run sharing this database.
        await session.execute(text("DELETE FROM agent_definitions"))
        await session.execute(text("DELETE FROM vault_keys"))
    yield


async def _user_id(client: AsyncClient, headers: dict[str, str]) -> UUID:
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return UUID(response.json()["data"]["id"])


async def _store_key(client: AsyncClient, headers: dict[str, str], name: str) -> UUID:
    response = await client.post(
        "/api/v1/vault", headers=headers, json={"raw_key": RAW_KEY, "name": name}
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_status_reports_the_active_key_and_row_counts(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _store_key(client, auth_headers(fx["user_access"]), "cli-status")

    assert await keys_cli._async_main(["status"]) == keys_cli.EXIT_OK

    out = capsys.readouterr().out
    assert kek_registry.active_kek(kek_registry.Purpose.VAULT)[1] in out
    assert envelope.SCHEME_V2 in out
    assert "No legacy-scheme rows" in out
    assert RAW_KEY not in out


@pytest.mark.asyncio
async def test_migrate_vault_dry_run_then_apply(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    user_id = await _user_id(client, auth_headers(fx["user_access"]))
    evidence_key, _ = kek_registry.active_kek(kek_registry.Purpose.EVIDENCE)

    async with session_scope() as session:
        session.add(
            VaultKey(
                user_id=user_id,
                service="openai",
                name="cli-legacy",
                kind="llm",
                encrypted_key=aes_vault.encrypt(RAW_KEY.encode(), evidence_key),
                scheme=envelope.SCHEME_LEGACY,
                key_prefix=RAW_KEY[:8] + "...",
                key_suffix="..." + RAW_KEY[-4:],
                is_active=True,
            )
        )

    assert await keys_cli._async_main(["migrate-vault"]) == keys_cli.EXIT_OK
    dry = capsys.readouterr().out
    assert "DRY RUN" in dry
    assert "re-sealed as v2     : 0" in dry

    assert await keys_cli._async_main(["migrate-vault", "--apply"]) == keys_cli.EXIT_OK
    applied = capsys.readouterr().out
    assert "APPLIED" in applied
    assert "re-sealed as v2     : 1" in applied
    assert "remaining legacy    : 0" in applied
    assert RAW_KEY not in applied


@pytest.mark.asyncio
async def test_rotate_warns_when_the_target_is_not_the_configured_active_kek(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _store_key(client, auth_headers(fx["user_access"]), "cli-rotate-warn")
    new_kek_b64 = base64.b64encode(secrets.token_bytes(32)).decode()

    assert (
        await keys_cli._async_main(["rotate", "--new-kek-b64", new_kek_b64])
        == keys_cli.EXIT_OK
    )
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "DRY RUN" in out


@pytest.mark.asyncio
async def test_rotate_apply_moves_every_row_to_the_new_kek(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _store_key(client, auth_headers(fx["user_access"]), "cli-rotate")

    new_kek = secrets.token_bytes(32)
    new_kek_id = envelope.kek_fingerprint(new_kek)
    argv = ["rotate", "--new-kek-b64", base64.b64encode(new_kek).decode(), "--apply"]

    assert await keys_cli._async_main(argv) == keys_cli.EXIT_OK
    out = capsys.readouterr().out
    assert f"target kek_id   : {new_kek_id}" in out
    assert "re-wrapped      : 1" in out

    async with session_scope() as session:
        rows = list(await session.scalars(select(VaultKey)))
        assert [row.kek_id for row in rows] == [new_kek_id]


@pytest.mark.asyncio
async def test_verify_is_clean_then_flags_a_corrupt_row(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    key_id = await _store_key(client, auth_headers(fx["user_access"]), "cli-verify")

    assert await keys_cli._async_main(["verify"]) == keys_cli.EXIT_OK
    assert "all rows decryptable" in capsys.readouterr().out

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        row.wrapped_dek = None
        await session.commit()

    assert await keys_cli._async_main(["verify"]) == keys_cli.EXIT_FAILURES
    out = capsys.readouterr().out
    assert str(key_id) in out
    assert RAW_KEY not in out


@pytest.mark.asyncio
async def test_rotate_rejects_a_bad_kek() -> None:
    with pytest.raises(SystemExit):
        await keys_cli._async_main(["rotate", "--new-kek-b64", "not base64!!"])
    with pytest.raises(SystemExit):
        await keys_cli._async_main(
            ["rotate", "--new-kek-b64", base64.b64encode(b"too short").decode()]
        )
