"""Tests for Ed25519 helpers."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from axiom.services.crypto import ed25519
from axiom.services.crypto.exceptions import CryptoInputError


def test_generate_keypair_unique() -> None:
    a = ed25519.generate_keypair()
    b = ed25519.generate_keypair()
    assert a.public_key_pem != b.public_key_pem


def test_sign_verify_round_trip() -> None:
    kp = ed25519.generate_keypair()
    msg = b"hello-axiom"
    sig = ed25519.sign(kp.private_key_pem, msg)
    assert ed25519.verify(kp.public_key_pem, msg, sig) is True


def test_verify_rejects_tampered_message() -> None:
    kp = ed25519.generate_keypair()
    msg = b"payload"
    sig = ed25519.sign(kp.private_key_pem, msg)
    assert ed25519.verify(kp.public_key_pem, msg + b"x", sig) is False


def test_verify_rejects_wrong_public_key() -> None:
    kp1 = ed25519.generate_keypair()
    kp2 = ed25519.generate_keypair()
    sig = ed25519.sign(kp1.private_key_pem, b"m")
    assert ed25519.verify(kp2.public_key_pem, b"m", sig) is False


def test_verify_rejects_malformed_signature() -> None:
    kp = ed25519.generate_keypair()
    with pytest.raises(CryptoInputError):
        ed25519.verify(kp.public_key_pem, b"m", b"\x00" * 63)


def test_stable_key_id_deterministic() -> None:
    kp = ed25519.generate_keypair()
    assert ed25519.stable_key_id(kp.public_key_pem) == ed25519.stable_key_id(kp.public_key_pem)


def test_stable_key_id_distinguishes() -> None:
    a = ed25519.generate_keypair()
    b = ed25519.generate_keypair()
    assert ed25519.stable_key_id(a.public_key_pem) != ed25519.stable_key_id(b.public_key_pem)


def test_sign_rejects_non_ed25519_pem() -> None:
    bad = SecretStr("not-valid-pem")
    with pytest.raises(CryptoInputError):
        ed25519.sign(bad, b"msg")
