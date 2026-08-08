"""Vault envelope encryption: dual-read, v2 writes, backfill, rotation (Phase 8.2)."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from axiom.core import errors
from axiom.db import session_scope
from axiom.models.vault import VaultKey
from axiom.services import vault as vault_service
from axiom.services import vault_rotation
from axiom.services.crypto import envelope, kek_registry
from axiom.services.crypto import vault as aes_vault
from axiom.services.crypto.exceptions import DecryptionError as CryptoDecryptionError
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key

RAW_KEY = "sk-proj-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture(autouse=True)
async def _isolate_vault_table() -> AsyncIterator[None]:
    """Backfill, rotation, and verify are whole-table operations.

    The test database is shared across the whole run (and across runs), so rows
    left by other modules — some sealed under a since-regenerated dev key —
    would otherwise show up as failures here. CASCADE also clears
    agent_definitions, which is the only table referencing vault_keys.
    """
    async with session_scope() as session:
        await session.execute(text("TRUNCATE vault_keys CASCADE"))
    yield


async def _user_id(client: AsyncClient, headers: dict[str, str]) -> UUID:
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return UUID(response.json()["data"]["id"])


async def _store_key(client: AsyncClient, headers: dict[str, str], name: str, raw: str) -> UUID:
    response = await client.post(
        "/api/v1/vault", headers=headers, json={"raw_key": raw, "name": name}
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def _seed_legacy_row(user_id: UUID, raw: str, name: str) -> UUID:
    """Write a row exactly as the pre-8.2 code did: AES-GCM under the evidence key."""
    evidence_key, _ = kek_registry.active_kek(kek_registry.Purpose.EVIDENCE)
    async with session_scope() as session:
        row = VaultKey(
            user_id=user_id,
            service="openai",
            name=name,
            kind="llm",
            encrypted_key=aes_vault.encrypt(raw.encode("utf-8"), evidence_key),
            scheme=envelope.SCHEME_LEGACY,
            key_prefix=raw[:8] + "...",
            key_suffix="..." + raw[-4:],
            is_active=True,
        )
        session.add(row)
        await session.flush()
        return row.id


@pytest.mark.asyncio
async def test_new_writes_are_v2_with_a_wrapped_dek(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    key_id = await _store_key(client, auth_headers(fx["user_access"]), "v2-write", RAW_KEY)

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        assert row.scheme == envelope.SCHEME_V2
        assert row.wrapped_dek
        assert row.kek_id
        assert vault_service.decrypt_row(row) == RAW_KEY


@pytest.mark.asyncio
async def test_new_writes_do_not_use_the_evidence_key(client: AsyncClient) -> None:
    """The whole point of the phase: the evidence key must not open a credential."""
    fx = await bootstrap_project_with_api_key(client)
    key_id = await _store_key(client, auth_headers(fx["user_access"]), "not-evidence", RAW_KEY)
    evidence_key, _ = kek_registry.active_kek(kek_registry.Purpose.EVIDENCE)

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        assert row.wrapped_dek is not None
        with pytest.raises(CryptoDecryptionError):
            aes_vault.decrypt(row.wrapped_dek, evidence_key)


@pytest.mark.asyncio
async def test_legacy_row_still_decrypts(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    user_id = await _user_id(client, auth_headers(fx["user_access"]))
    raw = "sk-proj-legacylegacylegacylegacylegac"
    key_id = await _seed_legacy_row(user_id, raw, "legacy-read")

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        assert row.scheme == envelope.SCHEME_LEGACY
        assert vault_service.decrypt_row(row) == raw


@pytest.mark.asyncio
async def test_v2_row_without_wrapped_dek_raises_rather_than_falling_back(
    client: AsyncClient,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    key_id = await _store_key(client, auth_headers(fx["user_access"]), "corrupt", RAW_KEY)

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        row.wrapped_dek = None
        await session.flush()
        with pytest.raises(errors.DecryptionError):
            vault_service.decrypt_row(row)


@pytest.mark.asyncio
async def test_ciphertext_moved_between_rows_fails(client: AsyncClient) -> None:
    """AAD binding: user A's ciphertext pasted onto user B's row must not open."""
    fx_a = await bootstrap_project_with_api_key(client)
    fx_b = await bootstrap_project_with_api_key(client)
    id_a = await _store_key(client, auth_headers(fx_a["user_access"]), "aad-a", RAW_KEY)
    id_b = await _store_key(
        client,
        auth_headers(fx_b["user_access"]),
        "aad-b",
        "sk-proj-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )

    async with session_scope() as session:
        row_a = await session.get(VaultKey, id_a)
        row_b = await session.get(VaultKey, id_b)
        assert row_a is not None and row_b is not None
        row_b.encrypted_key = row_a.encrypted_key
        row_b.wrapped_dek = row_a.wrapped_dek
        row_b.kek_id = row_a.kek_id
        await session.flush()
        with pytest.raises(errors.DecryptionError):
            vault_service.decrypt_row(row_b)


@pytest.mark.asyncio
async def test_backfill_reseals_legacy_rows_and_is_idempotent(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    user_id = await _user_id(client, auth_headers(fx["user_access"]))
    raw = "sk-proj-backfillbackfillbackfillbackf"
    key_id = await _seed_legacy_row(user_id, raw, "backfill-me")

    async with session_scope() as session:
        dry = await vault_rotation.backfill_legacy_rows(session, dry_run=True)
        assert dry.scanned == 1
        assert dry.resealed == 0

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        assert row.scheme == envelope.SCHEME_LEGACY, "dry run must not write"

    async with session_scope() as session:
        first = await vault_rotation.backfill_legacy_rows(session, dry_run=False)
        assert first.resealed == 1
        assert not first.failed

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        assert row.scheme == envelope.SCHEME_V2
        assert row.wrapped_dek
        assert vault_service.decrypt_row(row) == raw

    async with session_scope() as session:
        second = await vault_rotation.backfill_legacy_rows(session, dry_run=False)
        assert second.scanned == 0
        assert second.resealed == 0
        assert second.remaining_legacy == 0


@pytest.mark.asyncio
async def test_full_rotation_keeps_every_credential_readable(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    headers = auth_headers(fx["user_access"])
    expected = {
        await _store_key(client, headers, f"rot-{i}", f"sk-proj-{'r' * 20}{i:04d}"): (
            f"sk-proj-{'r' * 20}{i:04d}"
        )
        for i in range(3)
    }

    new_kek = secrets.token_bytes(32)
    new_kek_id = envelope.kek_fingerprint(new_kek)

    async with session_scope() as session:
        dry = await vault_rotation.rewrap_rows(
            session, new_kek=new_kek, new_kek_id=new_kek_id, dry_run=True
        )
        assert dry.scanned == 3
        assert dry.rewrapped == 0

    async with session_scope() as session:
        result = await vault_rotation.rewrap_rows(
            session, new_kek=new_kek, new_kek_id=new_kek_id, dry_run=False
        )
        assert result.rewrapped == 3
        assert not result.failed

    async with session_scope() as session:
        rows = list(
            await session.scalars(
                select(VaultKey).where(VaultKey.id.in_(list(expected.keys())))
            )
        )
        assert len(rows) == 3
        for row in rows:
            assert row.kek_id == new_kek_id
            secret = envelope.WrappedSecret(
                kek_id=row.kek_id,
                scheme=row.scheme,
                wrapped_dek=row.wrapped_dek or b"",
                ciphertext=row.encrypted_key,
            )
            aad = envelope.vault_aad(row.id, row.user_id)
            assert envelope.unseal(secret, new_kek, aad=aad).decode() == expected[row.id]


@pytest.mark.asyncio
async def test_rotation_is_resumable(client: AsyncClient) -> None:
    """A second pass finds nothing left to do, which is what 'resume' means here."""
    fx = await bootstrap_project_with_api_key(client)
    await _store_key(client, auth_headers(fx["user_access"]), "resume", RAW_KEY)

    new_kek = secrets.token_bytes(32)
    new_kek_id = envelope.kek_fingerprint(new_kek)

    async with session_scope() as session:
        await vault_rotation.rewrap_rows(
            session, new_kek=new_kek, new_kek_id=new_kek_id, dry_run=False
        )
    async with session_scope() as session:
        again = await vault_rotation.rewrap_rows(
            session, new_kek=new_kek, new_kek_id=new_kek_id, dry_run=False
        )
        assert again.rewrapped == 0
        assert again.already_current == again.scanned


@pytest.mark.asyncio
async def test_status_reports_scheme_and_key_counts(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    await _store_key(client, auth_headers(fx["user_access"]), "status-row", RAW_KEY)

    async with session_scope() as session:
        report = await vault_rotation.status(session)

    assert report.active_kek_id
    assert report.active_kek_id in report.known_kek_ids
    assert report.total_rows == 1
    assert report.rows_by_scheme == {envelope.SCHEME_V2: 1}
    assert report.oldest_row_age_days is not None


@pytest.mark.asyncio
async def test_verify_reports_a_corrupt_row_without_leaking_plaintext(
    client: AsyncClient,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    key_id = await _store_key(client, auth_headers(fx["user_access"]), "verify-bad", RAW_KEY)

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        row.wrapped_dek = None
        await session.commit()

    async with session_scope() as session:
        result = await vault_rotation.verify_rows(session)

    assert not result.clean
    failed_ids = [row_id for row_id, _ in result.failed]
    assert key_id in failed_ids
    assert all(RAW_KEY not in reason for _, reason in result.failed)


@pytest.mark.asyncio
async def test_stored_credential_round_trips_through_the_service(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    raw = "gsk_" + "g" * 40
    await _store_key(client, auth_headers(fx["user_access"]), "provider-lookup", raw)
    user_id = await _user_id(client, auth_headers(fx["user_access"]))

    async with session_scope() as session:
        found = await vault_service.get_key_for_provider(session, user_id, "groq")

    assert found == raw


@pytest.mark.asyncio
async def test_unknown_scheme_raises(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    key_id = await _store_key(client, auth_headers(fx["user_access"]), "weird-scheme", RAW_KEY)

    async with session_scope() as session:
        row = await session.get(VaultKey, key_id)
        assert row is not None
        row.scheme = "grace/vault/v99"
        await session.flush()
        with pytest.raises(errors.DecryptionError):
            vault_service.decrypt_row(row)
