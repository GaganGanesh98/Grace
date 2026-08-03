"""Tests for AES-256-GCM."""

from __future__ import annotations

import pytest

from axiom.core import errors
from axiom.services.crypto import aes_gcm


def test_encrypt_decrypt_round_trip() -> None:
    key = aes_gcm.generate_key()
    pt = b"secret evidence"
    ct = aes_gcm.encrypt(key, pt)
    assert aes_gcm.decrypt(key, ct) == pt


def test_decrypt_tampered_ciphertext_raises() -> None:
    key = aes_gcm.generate_key()
    ct = aes_gcm.encrypt(key, b"data")
    bad = aes_gcm.AESGCMCiphertext(
        nonce=ct.nonce,
        ciphertext=ct.ciphertext[:-1] + bytes([ct.ciphertext[-1] ^ 1]),
        key_id=ct.key_id,
    )
    with pytest.raises(errors.DecryptionError):
        aes_gcm.decrypt(key, bad)


def test_decrypt_wrong_key_raises() -> None:
    k1 = aes_gcm.generate_key()
    k2 = aes_gcm.generate_key()
    ct = aes_gcm.encrypt(k1, b"x")
    with pytest.raises(errors.DecryptionError):
        aes_gcm.decrypt(k2, ct)


def test_decrypt_wrong_aad_raises() -> None:
    key = aes_gcm.generate_key()
    ct = aes_gcm.encrypt(key, b"x", associated_data=b"aad")
    with pytest.raises(errors.DecryptionError):
        aes_gcm.decrypt(key, ct, associated_data=b"other")


def test_nonce_unique_across_encrypts() -> None:
    key = aes_gcm.generate_key()
    nonces = {aes_gcm.encrypt(key, b"x").nonce for _ in range(1000)}
    assert len(nonces) == 1000


def test_key_length_validation() -> None:
    with pytest.raises(ValueError):
        aes_gcm.encrypt(b"short", b"x")
    key = aes_gcm.generate_key()
    ct = aes_gcm.encrypt(key, b"x")
    with pytest.raises(ValueError):
        aes_gcm.decrypt(b"\x00" * 31, ct)
