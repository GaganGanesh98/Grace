"""Unit tests for hybrid Ed25519 + ML-DSA signatures."""

from __future__ import annotations

import pytest

from axiom.services.crypto import ed25519, hybrid, ml_dsa_65


def test_hybrid_round_trip() -> None:
    msg = b"hybrid-msg"
    esk, epk = ed25519.generate_keypair(raw=True)
    if ml_dsa_65.ML_DSA_AVAILABLE:
        msk, mpk = ml_dsa_65.generate_keypair()
    else:
        msk = b"\x00" * 32
        mpk = b"\x00" * 32
    sig = hybrid.hybrid_sign(msg, esk, msk)
    assert hybrid.hybrid_verify(msg, sig, epk, mpk) is True


@pytest.mark.skipif(not ml_dsa_65.ML_DSA_AVAILABLE, reason="ML-DSA not installed")
def test_partial_ml_signature_fails() -> None:
    msg = b"x"
    esk, epk = ed25519.generate_keypair(raw=True)
    msk, mpk = ml_dsa_65.generate_keypair()
    full = hybrid.hybrid_sign(msg, esk, msk)
    bad = hybrid.HybridSignature(ed25519_sig=full.ed25519_sig, ml_dsa_sig=b"")
    assert hybrid.hybrid_verify(msg, bad, epk, mpk) is False


def test_stub_mode_hybrid(caplog: pytest.LogCaptureFixture) -> None:
    if ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA is available; stub-mode test not applicable")
    msg = b"stub"
    esk, epk = ed25519.generate_keypair(raw=True)
    sig = hybrid.hybrid_sign(msg, esk, b"\x00" * 32)
    assert sig.ml_dsa_sig == b""
    caplog.set_level("WARNING")
    assert hybrid.hybrid_verify(msg, sig, epk, b"\x00" * 32) is True
    assert any("Skipping ML-DSA" in r.message for r in caplog.records)


def test_stub_mode_rejects_nonempty_ml_signature(caplog: pytest.LogCaptureFixture) -> None:
    if ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA is available")
    msg = b"x"
    esk, epk = ed25519.generate_keypair(raw=True)
    bad = hybrid.HybridSignature(ed25519_sig=ed25519.sign(msg, esk), ml_dsa_sig=b"\x01")
    caplog.set_level("WARNING")
    assert hybrid.hybrid_verify(msg, bad, epk, b"\x00" * 32) is False
    assert any("non-empty" in r.message for r in caplog.records)
