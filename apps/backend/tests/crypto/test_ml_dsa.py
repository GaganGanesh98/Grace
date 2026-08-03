"""Tests for ML-DSA-65 helpers."""

from __future__ import annotations

from axiom.services.crypto import ml_dsa


def test_generate_keypair_unique() -> None:
    a = ml_dsa.generate_keypair()
    b = ml_dsa.generate_keypair()
    assert a.public_key_bytes != b.public_key_bytes


def test_sign_verify_round_trip() -> None:
    kp = ml_dsa.generate_keypair()
    msg = b"hello-pq"
    sig = ml_dsa.sign(kp.private_key_bytes, msg)
    assert ml_dsa.verify(kp.public_key_bytes, msg, sig) is True


def test_verify_rejects_tampered_message() -> None:
    kp = ml_dsa.generate_keypair()
    msg = b"payload"
    sig = ml_dsa.sign(kp.private_key_bytes, msg)
    assert ml_dsa.verify(kp.public_key_bytes, msg + b"x", sig) is False


def test_verify_rejects_wrong_public_key() -> None:
    k1 = ml_dsa.generate_keypair()
    k2 = ml_dsa.generate_keypair()
    sig = ml_dsa.sign(k1.private_key_bytes, b"m")
    assert ml_dsa.verify(k2.public_key_bytes, b"m", sig) is False


def test_verify_rejects_malformed_signature() -> None:
    kp = ml_dsa.generate_keypair()
    assert ml_dsa.verify(kp.public_key_bytes, b"m", b"\x00" * 8) is False


def test_stable_key_id_deterministic() -> None:
    kp = ml_dsa.generate_keypair()
    assert ml_dsa.stable_key_id(kp.public_key_bytes) == ml_dsa.stable_key_id(kp.public_key_bytes)


def test_stable_key_id_distinguishes() -> None:
    a = ml_dsa.generate_keypair()
    b = ml_dsa.generate_keypair()
    assert ml_dsa.stable_key_id(a.public_key_bytes) != ml_dsa.stable_key_id(b.public_key_bytes)


def test_ml_dsa_signature_length() -> None:
    kp = ml_dsa.generate_keypair()
    sig = ml_dsa.sign(kp.private_key_bytes, b"x")
    assert len(sig) == 3309


def test_ml_dsa_public_key_length() -> None:
    kp = ml_dsa.generate_keypair()
    assert len(kp.public_key_bytes) == 1952
