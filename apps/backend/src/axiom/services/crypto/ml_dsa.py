"""ML-DSA-65 (FIPS 204) signing using ``dilithium-py``."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import cast

from dilithium_py.ml_dsa import ML_DSA_65
from pydantic import SecretBytes


@dataclass(frozen=True)
class MLDSAKeyPair:
    private_key_bytes: SecretBytes
    public_key_bytes: bytes
    key_id: str


def generate_keypair() -> MLDSAKeyPair:
    public_key, private_key = ML_DSA_65.keygen()
    return MLDSAKeyPair(
        private_key_bytes=SecretBytes(private_key),
        public_key_bytes=public_key,
        key_id=stable_key_id(public_key),
    )


def sign(private_key_bytes: SecretBytes, message: bytes) -> bytes:
    sk = private_key_bytes.get_secret_value()
    return cast(bytes, ML_DSA_65.sign(sk, message))


def verify(public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Return True iff the signature is valid. Invalid inputs return False (never raises)."""
    try:
        return bool(ML_DSA_65.verify(public_key_bytes, message, signature))
    except (ValueError, TypeError):
        return False


def stable_key_id(public_key_bytes: bytes) -> str:
    return hashlib.sha256(public_key_bytes).hexdigest()
