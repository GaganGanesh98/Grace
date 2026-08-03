"""Presented-key verification for ``/v1/govern`` and ``/v1/disclose``.

Contract:
  * The caller sends ``Authorization: Bearer axm_live_<random>`` (or the
    ``X-Api-Key`` header — both accepted).
  * We hash the presented secret with SHA-256 and compare to the stored
    ``key_hash`` using ``hmac.compare_digest``.
  * A present-but-revoked or expired key returns None to the caller, who
    surfaces 401.
  * A valid key returns an ``APIKeyContext`` binding ``project_id``,
    ``api_key_id``, and the key's scope list.

Scope enforcement is the router's job; this module only reports what the
key is allowed to do.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.api_key import ApiKey


class APIKeyVerificationError(Exception):
    """Raised when a presented key is malformed."""


@dataclass(frozen=True)
class APIKeyContext:
    api_key_id: UUID
    project_id: UUID
    created_by_user_id: UUID
    scopes: tuple[str, ...]
    key_prefix: str


_VALID_PREFIXES: tuple[str, ...] = ("axm_live_", "axm_test_")


def _hash_presented(presented: str) -> str:
    return hashlib.sha256(presented.encode("utf-8")).hexdigest()


def _looks_like_key(presented: str) -> bool:
    return any(presented.startswith(p) for p in _VALID_PREFIXES)


async def verify_key(
    session: AsyncSession,
    presented: str,
    *,
    required_scope: str | None = None,
) -> APIKeyContext | None:
    """Return an ``APIKeyContext`` for a valid, active, in-scope key; else None.

    Constant-time comparison is applied AFTER narrowing by ``key_prefix``.
    The prefix narrows the search space from all keys to usually zero or one
    candidate; within that candidate we use ``hmac.compare_digest`` so an
    attacker can't distinguish "wrong prefix" from "wrong secret" by timing.
    """

    if not presented or not _looks_like_key(presented):
        return None
    if len(presented) < 16:
        return None

    prefix = presented[:16]
    rows = await session.scalars(
        select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.revoked_at.is_(None),
        )
    )
    candidates = list(rows)
    if not candidates:
        hmac.compare_digest(  # absorb a compare so timing doesn't fingerprint miss-vs-hit
            "0" * 64,
            "1" * 64,
        )
        return None

    presented_hash = _hash_presented(presented)
    match: ApiKey | None = None
    for candidate in candidates:
        if hmac.compare_digest(presented_hash, candidate.key_hash):
            match = candidate
            break
    if match is None:
        return None

    if match.expires_at is not None and match.expires_at < datetime.now(UTC):
        return None

    scopes = tuple(match.scopes or ())
    if required_scope is not None and required_scope not in scopes:
        return None

    return APIKeyContext(
        api_key_id=match.id,
        project_id=match.project_id,
        created_by_user_id=match.created_by_user_id,
        scopes=scopes,
        key_prefix=match.key_prefix,
    )
