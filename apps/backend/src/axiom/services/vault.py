"""Encrypt and manage user-scoped credentials (vault)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.models.agent_definition import AgentDefinition
from axiom.models.vault import VaultKey
from axiom.services.crypto import vault as aes_vault
from axiom.services.receipt.keys import get_signing_keys

logger = structlog.get_logger(__name__)

_KIND_SET = frozenset({"llm", "tool", "custom"})

DETECTION_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^sk-ant-"), "llm", "anthropic"),
    (re.compile(r"^gsk_"), "llm", "groq"),
    (re.compile(r"^sk-proj-"), "llm", "openai"),
    (re.compile(r"^sk-"), "llm", "openai"),
    (re.compile(r"^AIza[A-Za-z0-9_-]{35}$"), "llm", "google"),
    (re.compile(r"^xai-"), "llm", "xai"),
    (re.compile(r"^(claude|cl)_"), "llm", "anthropic"),
    (re.compile(r"^ghp_"), "tool", "github"),
    (re.compile(r"^github_pat_"), "tool", "github"),
    (re.compile(r"^xoxb-"), "tool", "slack"),
    (re.compile(r"^xoxp-"), "tool", "slack"),
    (re.compile(r"^xoxa-"), "tool", "slack"),
    (re.compile(r"^xapp-"), "tool", "slack"),
    (re.compile(r"^AKIA[0-9A-Z]{16}$"), "tool", "aws"),
    (re.compile(r"^ya29\."), "tool", "google-oauth"),
    (re.compile(r"^ntn_"), "tool", "notion"),
    (re.compile(r"^figd_"), "tool", "figma"),
    (re.compile(r"^pat-"), "tool", "airtable"),
    (re.compile(r"^r8_"), "llm", "replicate"),
]


def detect_credential_kind_and_service(raw_key: str) -> tuple[str, str]:
    """Detect (kind, service) from credential prefix.

    Returns ('custom', 'custom') if no rule matches — caller can require
    user to specify service manually.
    """
    for pattern, kind, service in DETECTION_RULES:
        if pattern.match(raw_key):
            return (kind, service)
    return ("custom", "custom")


def _display_prefix(raw: str) -> str:
    if len(raw) <= 8:
        return raw
    return raw[:8] + "..."


def _display_suffix(raw: str) -> str:
    if len(raw) <= 4:
        return raw
    return "..." + raw[-4:]


def _encryption_key() -> bytes:
    return get_signing_keys().evidence_key


@dataclass(frozen=True)
class VaultKeyDisplay:
    id: UUID
    service: str
    name: str
    kind: str
    key_prefix: str
    key_suffix: str
    is_active: bool
    created_at: datetime


def _to_display(row: VaultKey) -> VaultKeyDisplay:
    return VaultKeyDisplay(
        id=row.id,
        service=row.service,
        name=row.name,
        kind=row.kind,
        key_prefix=row.key_prefix,
        key_suffix=row.key_suffix,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def _resolve_kind_service(
    raw_key: str,
    *,
    kind_override: str | None,
    service_override: str | None,
) -> tuple[str, str]:
    d_kind, d_service = detect_credential_kind_and_service(raw_key.strip())
    kind_s = (kind_override or "").strip().lower()
    if kind_s in _KIND_SET:
        res_kind = kind_s
    else:
        res_kind = d_kind
    svc_s = (service_override or "").strip()
    if svc_s:
        res_service = svc_s[:50]
    elif d_service != "custom":
        res_service = d_service[:50]
    else:
        res_service = "custom"
    return res_kind, res_service


async def create_vault_key(
    db: AsyncSession,
    user_id: UUID,
    name: str,
    raw_key: str,
    *,
    kind_override: str | None = None,
    service_override: str | None = None,
) -> tuple[VaultKey, str, str]:
    """Encrypt and store a credential. Returns (row, detected_kind, detected_service)."""
    if not raw_key.strip():
        raise errors.ValidationError("API key must not be empty")

    d_kind, d_service = detect_credential_kind_and_service(raw_key.strip())
    res_kind, res_service = _resolve_kind_service(
        raw_key, kind_override=kind_override, service_override=service_override
    )
    if res_kind not in _KIND_SET:
        raise errors.ValidationError("kind must be one of: llm, tool, custom")

    enc = aes_vault.encrypt(raw_key.encode("utf-8"), _encryption_key())

    row = VaultKey(
        user_id=user_id,
        service=res_service,
        name=name.strip()[:100],
        kind=res_kind,
        encrypted_key=enc,
        key_prefix=_display_prefix(raw_key),
        key_suffix=_display_suffix(raw_key),
        is_active=True,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise errors.ConflictError("A key with this service and name already exists.") from exc

    logger.info(
        "vault.key_stored",
        user_id=str(user_id),
        service=res_service,
        kind=res_kind,
        vault_key_id=str(row.id),
    )
    return row, d_kind, d_service


async def _active_llm_key_row(
    db: AsyncSession, user_id: UUID, service: str
) -> VaultKey | None:
    return await db.scalar(
        select(VaultKey)
        .where(
            VaultKey.user_id == user_id,
            VaultKey.service == service,
            VaultKey.kind == "llm",
            VaultKey.is_active.is_(True),
        )
        .order_by(VaultKey.created_at.desc())
        .limit(1)
    )


async def get_key_for_provider(db: AsyncSession, user_id: UUID, service: str) -> str | None:
    """Decrypt and return the active LLM key for a service, or None."""
    row = await _active_llm_key_row(db, user_id, service)
    if row is None:
        return None
    return aes_vault.decrypt(row.encrypted_key, _encryption_key()).decode("utf-8")


async def get_key_and_id_for_provider(
    db: AsyncSession, user_id: UUID, service: str
) -> tuple[str, UUID] | None:
    """Return (decrypted_key, vault_key_id) for the active LLM service key, or None."""
    row = await _active_llm_key_row(db, user_id, service)
    if row is None:
        return None
    raw = aes_vault.decrypt(row.encrypted_key, _encryption_key()).decode("utf-8")
    return raw, row.id


async def get_key_and_id_by_name(
    db: AsyncSession, user_id: UUID, name: str
) -> tuple[str, UUID] | None:
    """Return (decrypted_key, vault_key_id) for an active key named ``name``, or None.

    Used by the generic proxy, where the caller names the credential explicitly
    rather than having it inferred from a provider. Unlike the provider lookup
    this does not filter on ``kind``: an arbitrary HTTP target may legitimately
    need a 'tool' or 'custom' credential, and the caller has already stated
    which key it wants by name.

    Scoping to ``user_id`` is the tenancy boundary — a name belonging to another
    user resolves to None, which callers surface as not-found rather than
    forbidden so the vault cannot be enumerated.
    """
    row = await db.scalar(
        select(VaultKey)
        .where(
            VaultKey.user_id == user_id,
            VaultKey.name == name,
            VaultKey.is_active.is_(True),
        )
        .order_by(VaultKey.created_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    raw = aes_vault.decrypt(row.encrypted_key, _encryption_key()).decode("utf-8")
    return raw, row.id


async def get_vault_key(db: AsyncSession, user_id: UUID, key_id: UUID) -> VaultKeyDisplay:
    row = await db.get(VaultKey, key_id)
    if row is None or row.user_id != user_id:
        raise errors.ProjectNotFoundError("Vault key not found.")
    return _to_display(row)


async def update_vault_key(
    db: AsyncSession,
    user_id: UUID,
    key_id: UUID,
    *,
    name: str | None = None,
    is_active: bool | None = None,
) -> VaultKeyDisplay:
    row = await db.get(VaultKey, key_id)
    if row is None or row.user_id != user_id:
        raise errors.ProjectNotFoundError("Vault key not found.")
    if name is not None:
        row.name = name.strip()[:100]
    if is_active is not None:
        row.is_active = is_active
    return _to_display(row)


async def deactivate_vault_key(db: AsyncSession, user_id: UUID, key_id: UUID) -> VaultKeyDisplay:
    row = await db.get(VaultKey, key_id)
    if row is None or row.user_id != user_id:
        raise errors.ProjectNotFoundError("Vault key not found.")
    row.is_active = False
    return _to_display(row)


async def list_keys(
    db: AsyncSession, user_id: UUID, *, kind: str | None = None
) -> list[VaultKeyDisplay]:
    stmt = select(VaultKey).where(VaultKey.user_id == user_id)
    if kind is not None:
        k = kind.strip().lower()
        if k not in _KIND_SET:
            raise errors.ValidationError("kind must be one of: llm, tool, custom")
        stmt = stmt.where(VaultKey.kind == k)
    stmt = stmt.order_by(VaultKey.created_at.desc())
    rows = list(await db.scalars(stmt))
    return [_to_display(r) for r in rows]


async def delete_key(db: AsyncSession, user_id: UUID, key_id: UUID) -> UUID:
    row = await db.get(VaultKey, key_id)
    if row is None or row.user_id != user_id:
        raise errors.ProjectNotFoundError("Vault key not found.")

    stmt = select(AgentDefinition.id, AgentDefinition.name).where(
        AgentDefinition.vault_key_id == key_id
    )
    ref_rows = (await db.execute(stmt)).all()
    if ref_rows:
        raise errors.VaultKeyInUseError(referencing_agents=[(r[0], r[1]) for r in ref_rows])

    await db.delete(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(
            "vault.delete.integrity_error",
            vault_key_id=str(key_id),
            user_id=str(user_id),
            exc_info=True,
        )
        stmt2 = select(AgentDefinition.id, AgentDefinition.name).where(
            AgentDefinition.vault_key_id == key_id
        )
        ref2 = (await db.execute(stmt2)).all()
        if ref2:
            agents = [(r[0], r[1]) for r in ref2]
            raise errors.VaultKeyInUseError(referencing_agents=agents) from exc
        raise errors.VaultKeyInUseError(
            referencing_agents=[],
            message="Cannot delete: the key is still referenced (concurrent update).",
        ) from exc

    return key_id


# Backwards compatibility aliases used by tests / older call sites
async def store_key(
    db: AsyncSession,
    user_id: UUID,
    service: str | None,
    name: str,
    raw_key: str,
) -> tuple[VaultKey, str]:
    """Legacy: encrypt and store; returns (row, detected_service label)."""
    row, d_kind, d_service = await create_vault_key(
        db,
        user_id,
        name,
        raw_key,
        service_override=service,
    )
    return row, d_service if d_service != "custom" else "unknown"
