"""AES-256-GCM vault helpers (nonce prepended)."""

from __future__ import annotations

import hashlib
import secrets
from contextlib import suppress

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .audit import log_encrypt
from ._util import validate_bytes
from .exceptions import CryptoInputError, DecryptionError, NonceReuseError

__all__ = ["CryptoInputError", "DecryptionError", "NonceReuseError", "decrypt", "encrypt"]

# In-process nonce registry: detects RNG collisions or pathological repeats. Does not
# persist across restarts and does not defend against intentional cross-session reuse.
_seen_nonces: set[bytes] = set()


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with AES-256-GCM; returns ``nonce (12) || ciphertext || tag``."""
    validate_bytes(plaintext, "plaintext", min_len=1)
    validate_bytes(key, "key", exact_len=32)
    key_fp = hashlib.sha256(key).hexdigest()[:16]
    nonce = secrets.token_bytes(12)
    if nonce in _seen_nonces:
        raise NonceReuseError(
            "AES-GCM nonce collision in-process — RNG failure or reuse guard triggered",
        )
    _seen_nonces.add(nonce)
    aesgcm = AESGCM(key)
    try:
        ct = aesgcm.encrypt(nonce, plaintext, None)
    except (TypeError, ValueError) as exc:
        with suppress(Exception):
            log_encrypt(key_fp, len(plaintext), success=False)
        raise CryptoInputError("AES-GCM encryption failed") from exc
    out = nonce + ct
    with suppress(Exception):
        log_encrypt(key_fp, len(plaintext), success=True)
    return out


def decrypt(ciphertext_with_nonce: bytes, key: bytes) -> bytes:
    """Decrypt a value produced by :func:`encrypt`."""
    validate_bytes(key, "key", exact_len=32)
    validate_bytes(ciphertext_with_nonce, "ciphertext", min_len=28)
    nonce = ciphertext_with_nonce[:12]
    ct = ciphertext_with_nonce[12:]
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ct, None)
    except InvalidTag as exc:
        raise DecryptionError("AES-GCM authentication failed") from exc
    except (TypeError, ValueError) as exc:
        raise DecryptionError("AES-GCM decryption failed") from exc
