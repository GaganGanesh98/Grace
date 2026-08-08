"""Envelope encryption for stored secrets (Phase 8.2).

Every secret gets its own random 256-bit data key (DEK). The DEK encrypts the
payload; the key-encryption key (KEK) only ever wraps the DEK. Rotating a KEK is
therefore an unwrap/re-wrap of 32 bytes per row — it never touches the payload
plaintext, never needs the upstream provider, and is fast enough to run online.

Layout of both AEAD blobs is ``nonce (12) || ciphertext || tag``, matching
:mod:`axiom.services.crypto.vault` so the two are visually comparable.

Two independent AAD bindings:

* the payload is bound to its row identity (see :func:`vault_aad`), so a
  ciphertext moved to a different row or user fails the GCM tag;
* the wrapped DEK is bound to the ``kek_id`` recorded beside it, so a wrapped
  DEK cannot be replayed under a different key identifier.

This module is a leaf: it must not import routers, models, middleware, or the
DB layer (``.importlinter`` contract 3).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ._util import validate_bytes, zero_memory
from .exceptions import CryptoInputError, DecryptionError

__all__ = [
    "SCHEME_LEGACY",
    "SCHEME_V2",
    "WrappedSecret",
    "kek_fingerprint",
    "rewrap",
    "seal",
    "unseal",
    "vault_aad",
]

#: Rows written before Phase 8.2: ``encrypted_key`` is AES-GCM under the
#: evidence key with no AAD and no key identifier.
SCHEME_LEGACY = "legacy/v1"

#: Envelope scheme introduced by Phase 8.2. A future scheme gets a new value
#: rather than a redefinition of this one.
SCHEME_V2 = "grace/vault/v2"

_NONCE_LEN = 12
_DEK_LEN = 32
_KEK_LEN = 32
_MIN_BLOB_LEN = _NONCE_LEN + 16  # nonce + GCM tag, empty plaintext


@dataclass(frozen=True)
class WrappedSecret:
    """A sealed payload plus everything needed to find the key that opens it."""

    #: Identifier of the KEK that wrapped :attr:`wrapped_dek`.
    kek_id: str
    #: Envelope scheme; readers dispatch on this.
    scheme: str
    #: ``nonce || AESGCM(kek, dek)``
    wrapped_dek: bytes
    #: ``nonce || AESGCM(dek, plaintext, aad)``
    ciphertext: bytes


def kek_fingerprint(kek: bytes) -> str:
    """Stable, domain-separated identifier for a KEK.

    Truncated to 32 hex chars: long enough that a collision is not a concern,
    short enough to read in ``keys status`` output.
    """
    validate_bytes(kek, "kek", exact_len=_KEK_LEN)
    return hashlib.sha256(b"grace/kek-id/v1|" + kek).hexdigest()[:32]


def vault_aad(vault_key_id: UUID | str, user_id: UUID | str) -> bytes:
    """Bind a vault ciphertext to the row and user it belongs to.

    An attacker with write access to the database cannot move a ciphertext
    between rows or between users: the GCM tag fails. This costs nothing and
    closes a class of attack that confidentiality alone does not.
    """
    return f"{SCHEME_V2}|{vault_key_id}|{user_id}".encode()


def _dek_aad(kek_id: str) -> bytes:
    return f"grace/vault/dek/v1|{kek_id}".encode()


def _aead_seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = secrets.token_bytes(_NONCE_LEN)
    try:
        return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise CryptoInputError("AES-GCM encryption failed") from exc


def _aead_open(key: bytes, blob: bytes, aad: bytes) -> bytes:
    validate_bytes(blob, "ciphertext", min_len=_MIN_BLOB_LEN)
    try:
        return AESGCM(key).decrypt(blob[:_NONCE_LEN], blob[_NONCE_LEN:], aad)
    except InvalidTag as exc:
        raise DecryptionError("AES-GCM authentication failed") from exc
    except (TypeError, ValueError) as exc:
        raise DecryptionError("AES-GCM decryption failed") from exc


def _require_kek_id(kek_id: str) -> str:
    value = kek_id.strip()
    if not value:
        raise CryptoInputError("kek_id must not be empty")
    return value


def seal(plaintext: bytes, kek: bytes, *, kek_id: str, aad: bytes) -> WrappedSecret:
    """Encrypt ``plaintext`` under a fresh DEK and wrap that DEK with ``kek``."""
    validate_bytes(plaintext, "plaintext", min_len=1)
    validate_bytes(kek, "kek", exact_len=_KEK_LEN)
    resolved_id = _require_kek_id(kek_id)

    dek = bytearray(secrets.token_bytes(_DEK_LEN))
    try:
        ciphertext = _aead_seal(bytes(dek), plaintext, aad)
        wrapped_dek = _aead_seal(kek, bytes(dek), _dek_aad(resolved_id))
    finally:
        zero_memory(dek)

    return WrappedSecret(
        kek_id=resolved_id,
        scheme=SCHEME_V2,
        wrapped_dek=wrapped_dek,
        ciphertext=ciphertext,
    )


def unseal(secret: WrappedSecret, kek: bytes, *, aad: bytes) -> bytes:
    """Unwrap the DEK with ``kek``, then decrypt the payload."""
    validate_bytes(kek, "kek", exact_len=_KEK_LEN)
    if secret.scheme != SCHEME_V2:
        raise CryptoInputError(f"unsupported envelope scheme: {secret.scheme!r}")

    dek = bytearray(_aead_open(kek, secret.wrapped_dek, _dek_aad(secret.kek_id)))
    try:
        return _aead_open(bytes(dek), secret.ciphertext, aad)
    finally:
        zero_memory(dek)


def rewrap(
    secret: WrappedSecret,
    old_kek: bytes,
    new_kek: bytes,
    *,
    new_kek_id: str,
) -> WrappedSecret:
    """Re-wrap the DEK under a new KEK, leaving the payload untouched.

    The returned ``ciphertext`` is the same object as the input's. That is the
    property that keeps rotation cheap, and ``tests/crypto/test_envelope.py``
    asserts it — if this ever starts decrypting the payload, rotation stops
    being an online operation.
    """
    validate_bytes(old_kek, "old_kek", exact_len=_KEK_LEN)
    validate_bytes(new_kek, "new_kek", exact_len=_KEK_LEN)
    if secret.scheme != SCHEME_V2:
        raise CryptoInputError(f"unsupported envelope scheme: {secret.scheme!r}")
    resolved_id = _require_kek_id(new_kek_id)

    dek = bytearray(_aead_open(old_kek, secret.wrapped_dek, _dek_aad(secret.kek_id)))
    try:
        wrapped_dek = _aead_seal(new_kek, bytes(dek), _dek_aad(resolved_id))
    finally:
        zero_memory(dek)

    return WrappedSecret(
        kek_id=resolved_id,
        scheme=secret.scheme,
        wrapped_dek=wrapped_dek,
        ciphertext=secret.ciphertext,
    )
