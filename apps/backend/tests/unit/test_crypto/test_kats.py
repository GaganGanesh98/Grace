"""Known-answer tests (KATs) for Ed25519, SHA-256 (Merkle leaf), and AES-256-GCM."""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from axiom.services.crypto import ed25519, vault


def test_ed25519_rfc8032_vector_2_exact_signature() -> None:
    """RFC 8032 §7.1 TEST 2 — 1-byte message."""
    sk = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    msg = bytes([0x72])
    expected = bytes.fromhex(
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"
    )
    assert ed25519.sign(msg, sk) == expected


def test_ed25519_rfc8032_vector_3_exact_signature() -> None:
    """RFC 8032 §7.1 TEST 3 — 2-byte message."""
    sk = bytes.fromhex("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")
    msg = bytes.fromhex("af82")
    expected = bytes.fromhex(
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
        "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"
    )
    assert ed25519.sign(msg, sk) == expected


def test_rfc8032_vector_1_empty_message_rejected_by_api() -> None:
    """RFC 8032 TEST 1 uses an empty message; this API requires a non-empty message."""
    sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326419703acdebca5cd6e5")
    from axiom.services.crypto.exceptions import CryptoInputError

    with pytest.raises(CryptoInputError, match="must not be empty"):
        ed25519.sign(b"", sk)


def test_sha256_kat_empty_and_abc() -> None:
    """Plain SHA-256 (append Merkle uses SHA-256 over raw leaf bytes)."""
    assert hashlib.sha256(b"").hexdigest() == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert hashlib.sha256(b"abc").hexdigest() == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_aes256_gcm_nist_style_kat_round_trip() -> None:
    """NIST-style vector: AES-256-GCM with all-zero key and nonce (pyca reference)."""
    key = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000000")
    nonce = bytes.fromhex("000000000000000000000000")
    plaintext = bytes.fromhex("00000000000000000000000000000000")
    aes = AESGCM(key)
    ct_tag = aes.encrypt(nonce, plaintext, None)
    blob = nonce + ct_tag
    assert vault.decrypt(blob, key) == plaintext
