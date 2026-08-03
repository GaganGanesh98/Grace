"""Unit tests for AES-256-GCM vault helpers."""

from __future__ import annotations

import pytest

from axiom.services.crypto import vault

# Static 32-byte dev keys (ADR-026 — not production KMS material)
_KEY_A = b"k" * 32
_KEY_B = b"j" * 32


def test_encrypt_decrypt_round_trip() -> None:
    pt = b"secret-payload"
    ct = vault.encrypt(pt, _KEY_A)
    assert vault.decrypt(ct, _KEY_A) == pt


def test_decrypt_wrong_key_fails() -> None:
    ct = vault.encrypt(b"data", _KEY_A)
    with pytest.raises(vault.DecryptionError, match="authentication"):
        vault.decrypt(ct, _KEY_B)


def test_decrypt_tampered_ciphertext_fails() -> None:
    ct = bytearray(vault.encrypt(b"data", _KEY_A))
    ct[-1] ^= 0x01
    with pytest.raises(vault.DecryptionError, match="authentication"):
        vault.decrypt(bytes(ct), _KEY_A)


def test_encrypt_rejects_bad_key_length() -> None:
    with pytest.raises(vault.CryptoInputError, match="exactly 32"):
        vault.encrypt(b"x", b"short")


def test_decrypt_rejects_short_blob() -> None:
    with pytest.raises(vault.CryptoInputError, match="at least 28"):
        vault.decrypt(b"\x00" * 8, _KEY_A)
