"""Tests for ML-DSA-65 (pqcrypto or liboqs)."""

from __future__ import annotations

import pytest

from axiom.services.crypto import ml_dsa_65
from axiom.services.crypto.exceptions import KeyError_


def test_stub_raises_on_generate_when_unavailable() -> None:
    if ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA backend loaded")
    with pytest.raises(KeyError_, match="pqcrypto"):
        ml_dsa_65.generate_keypair()


def test_stub_verify_returns_false() -> None:
    if ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA backend loaded")
    sig = b"\x00" * ml_dsa_65.ML_DSA65_SIGNATURE_BYTES
    pk = b"\x00" * ml_dsa_65.ML_DSA65_PUBLIC_KEY_BYTES
    assert ml_dsa_65.verify(b"m", sig, pk) is False


def test_real_generate_sign_verify_round_trip() -> None:
    if not ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA backend not installed")
    sk, pk = ml_dsa_65.generate_keypair()
    assert len(sk) > 0 and len(pk) > 0
    msg = b"ml-dsa-65 round-trip"
    sig = ml_dsa_65.sign(msg, sk)
    assert ml_dsa_65.verify(msg, sig, pk) is True


def test_real_verify_rejects_tampered_message() -> None:
    if not ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA backend not installed")
    sk, pk = ml_dsa_65.generate_keypair()
    msg = b"payload"
    sig = ml_dsa_65.sign(msg, sk)
    assert ml_dsa_65.verify(msg + b"x", sig, pk) is False


def test_real_verify_rejects_wrong_public_key() -> None:
    if not ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA backend not installed")
    sk1, _ = ml_dsa_65.generate_keypair()
    _, pk2 = ml_dsa_65.generate_keypair()
    msg = b"m"
    sig = ml_dsa_65.sign(msg, sk1)
    assert ml_dsa_65.verify(msg, sig, pk2) is False
