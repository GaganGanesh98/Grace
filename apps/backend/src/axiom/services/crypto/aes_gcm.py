"""AES-256-GCM authenticated encryption."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from axiom.core import errors


@dataclass(frozen=True)
class AESGCMCiphertext:
    nonce: bytes
    ciphertext: bytes
    key_id: str


def generate_key() -> bytes:
    """Return a new random 32-byte AES-256 key."""
    return secrets.token_bytes(32)


def _key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()


def encrypt(key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> AESGCMCiphertext:
    if len(key) != 32:
        msg = "AES-256-GCM requires a 32-byte key"
        raise ValueError(msg)
    nonce = secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, associated_data)
    return AESGCMCiphertext(nonce=nonce, ciphertext=ct, key_id=_key_id(key))


def decrypt(
    key: bytes,
    ct: AESGCMCiphertext,
    associated_data: bytes | None = None,
) -> bytes:
    if len(key) != 32:
        msg = "AES-256-GCM requires a 32-byte key"
        raise ValueError(msg)
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(ct.nonce, ct.ciphertext, associated_data)
    except InvalidTag as exc:
        raise errors.DecryptionError("AES-GCM authentication failed") from exc
