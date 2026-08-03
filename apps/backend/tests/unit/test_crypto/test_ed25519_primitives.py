"""Unit tests for RFC 8032 raw Ed25519 helpers."""

from __future__ import annotations

from axiom.services.crypto import ed25519


def test_generate_sign_verify_round_trip() -> None:
    sk, pk = ed25519.generate_keypair(raw=True)
    msg = b"axiom-phase-1-75b"
    sig = ed25519.sign(msg, sk)
    assert ed25519.verify(msg, sig, pk) is True


def test_verify_wrong_key_fails() -> None:
    sk1, _pk1 = ed25519.generate_keypair(raw=True)
    _, pk2 = ed25519.generate_keypair(raw=True)
    msg = b"x"
    sig = ed25519.sign(msg, sk1)
    assert ed25519.verify(msg, sig, pk2) is False


def test_verify_tampered_message_fails() -> None:
    sk, pk = ed25519.generate_keypair(raw=True)
    msg = b"ok"
    sig = ed25519.sign(msg, sk)
    assert ed25519.verify(msg + b"!", sig, pk) is False


def test_legacy_pem_api_unchanged() -> None:
    kp = ed25519.generate_keypair()
    msg = b"legacy-pem"
    sig = ed25519.sign(kp.private_key_pem, msg)
    assert ed25519.verify(kp.public_key_pem, msg, sig) is True
