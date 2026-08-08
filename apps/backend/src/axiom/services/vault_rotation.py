"""Vault key maintenance: backfill, rotation, verification (Phase 8.2).

The operations behind ``axiom keys``. They live here rather than in the CLI so
they are testable without a subprocess, and so a future admin endpoint or
scheduled job can call the same code.

Every function commits per row rather than per batch. A rotation interrupted
halfway leaves a consistent database with a mix of ``kek_id`` values, which is
precisely the state the readers are built to handle — so "resume" is just
"run it again".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.vault import VaultKey
from axiom.services import vault as vault_service
from axiom.services.crypto import envelope, kek_registry

logger = structlog.get_logger(__name__)

__all__ = [
    "BackfillResult",
    "RotationResult",
    "VaultKeyStatus",
    "VerifyResult",
    "backfill_legacy_rows",
    "rewrap_rows",
    "status",
    "verify_rows",
]


@dataclass(frozen=True)
class VaultKeyStatus:
    """What ``keys status --purpose vault`` prints."""

    active_kek_id: str
    known_kek_ids: list[str]
    total_rows: int
    rows_by_scheme: dict[str, int]
    rows_by_kek_id: dict[str, int]
    oldest_row_age_days: float | None

    @property
    def legacy_rows(self) -> int:
        return self.rows_by_scheme.get(envelope.SCHEME_LEGACY, 0)


@dataclass
class BackfillResult:
    scanned: int = 0
    resealed: int = 0
    skipped: int = 0
    failed: list[tuple[UUID, str]] = field(default_factory=list)
    remaining_legacy: int = 0
    dry_run: bool = False


@dataclass
class RotationResult:
    scanned: int = 0
    rewrapped: int = 0
    already_current: int = 0
    failed: list[tuple[UUID, str]] = field(default_factory=list)
    new_kek_id: str = ""
    dry_run: bool = False


@dataclass
class VerifyResult:
    checked: int = 0
    ok: int = 0
    failed: list[tuple[UUID, str]] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.failed


async def status(db: AsyncSession) -> VaultKeyStatus:
    """Counts by scheme and by KEK — this is what tells you a rotation finished."""
    active_key, active_id = kek_registry.active_kek(kek_registry.Purpose.VAULT)
    del active_key

    by_scheme = {
        str(scheme): int(count)
        for scheme, count in (
            await db.execute(select(VaultKey.scheme, func.count()).group_by(VaultKey.scheme))
        ).all()
    }
    by_kek = {
        (kek_id or "<none>"): int(count)
        for kek_id, count in (
            await db.execute(select(VaultKey.kek_id, func.count()).group_by(VaultKey.kek_id))
        ).all()
    }
    oldest = await db.scalar(select(func.min(VaultKey.created_at)))
    age_days: float | None = None
    if oldest is not None:
        now = await db.scalar(select(func.now()))
        if now is not None:
            age_days = (now - oldest).total_seconds() / 86400.0

    return VaultKeyStatus(
        active_kek_id=active_id,
        known_kek_ids=kek_registry.known_kek_ids(kek_registry.Purpose.VAULT),
        total_rows=sum(by_scheme.values()),
        rows_by_scheme=by_scheme,
        rows_by_kek_id=by_kek,
        oldest_row_age_days=age_days,
    )


async def _count_legacy(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(VaultKey).where(
                VaultKey.scheme == envelope.SCHEME_LEGACY
            )
        )
        or 0
    )


async def backfill_legacy_rows(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> BackfillResult:
    """Re-seal ``legacy/v1`` rows as ``grace/vault/v2``.

    Idempotent: rows already on v2 are never selected, so a second run reports
    zero re-sealed. Resumable for the same reason.
    """
    result = BackfillResult(dry_run=dry_run)

    stmt = (
        select(VaultKey)
        .where(VaultKey.scheme == envelope.SCHEME_LEGACY)
        .order_by(VaultKey.created_at)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    for row in list(await db.scalars(stmt)):
        result.scanned += 1
        try:
            plaintext = vault_service.decrypt_row(row)
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the run
            result.failed.append((row.id, type(exc).__name__))
            logger.warning("vault.backfill.decrypt_failed", vault_key_id=str(row.id))
            continue

        if dry_run:
            result.skipped += 1
            continue

        sealed = vault_service.seal_credential(
            plaintext, vault_key_id=row.id, user_id=row.user_id
        )
        row.encrypted_key = sealed.ciphertext
        row.scheme = sealed.scheme
        row.kek_id = sealed.kek_id
        row.wrapped_dek = sealed.wrapped_dek
        await db.commit()
        result.resealed += 1
        logger.info("vault.backfill.resealed", vault_key_id=str(row.id), kek_id=sealed.kek_id)

    result.remaining_legacy = await _count_legacy(db)
    return result


async def rewrap_rows(
    db: AsyncSession,
    *,
    new_kek: bytes,
    new_kek_id: str,
    dry_run: bool = True,
    batch_size: int = 200,
) -> RotationResult:
    """Re-wrap every v2 row's DEK under ``new_kek``.

    The payload ciphertext is never touched — see ``envelope.rewrap``. Rows
    already carrying ``new_kek_id`` are skipped, which is what makes an
    interrupted rotation resumable.
    """
    result = RotationResult(new_kek_id=new_kek_id, dry_run=dry_run)
    offset = 0

    while True:
        rows = list(
            await db.scalars(
                select(VaultKey)
                .where(VaultKey.scheme == envelope.SCHEME_V2)
                .order_by(VaultKey.created_at)
                .offset(offset)
                .limit(batch_size)
            )
        )
        if not rows:
            break

        for row in rows:
            result.scanned += 1
            if row.kek_id == new_kek_id:
                result.already_current += 1
                continue
            if not row.wrapped_dek or not row.kek_id:
                result.failed.append((row.id, "MissingWrappedDek"))
                continue
            try:
                old_kek = kek_registry.kek_by_id(kek_registry.Purpose.VAULT, row.kek_id)
                rotated = envelope.rewrap(
                    envelope.WrappedSecret(
                        kek_id=row.kek_id,
                        scheme=row.scheme,
                        wrapped_dek=row.wrapped_dek,
                        ciphertext=row.encrypted_key,
                    ),
                    old_kek,
                    new_kek,
                    new_kek_id=new_kek_id,
                )
            except Exception as exc:  # noqa: BLE001 - report and continue
                result.failed.append((row.id, type(exc).__name__))
                logger.warning("vault.rotate.rewrap_failed", vault_key_id=str(row.id))
                continue

            if dry_run:
                continue

            row.kek_id = rotated.kek_id
            row.wrapped_dek = rotated.wrapped_dek
            await db.commit()
            result.rewrapped += 1

        # Rewrapped rows keep their position in the created_at ordering, so a
        # plain offset walk is stable here.
        offset += len(rows)

    return result


async def verify_rows(db: AsyncSession) -> VerifyResult:
    """Attempt an unseal of every row. Reports failures; never logs plaintext."""
    result = VerifyResult()
    for row in list(await db.scalars(select(VaultKey).order_by(VaultKey.created_at))):
        result.checked += 1
        try:
            plaintext = vault_service.decrypt_row(row)
        except Exception as exc:  # noqa: BLE001 - the point is to collect failures
            result.failed.append((row.id, type(exc).__name__))
            continue
        if plaintext:
            result.ok += 1
        else:
            result.failed.append((row.id, "EmptyPlaintext"))
    return result
