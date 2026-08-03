"""Unit tests for crypto audit logging."""

from __future__ import annotations

from structlog.testing import capture_logs

from axiom.services.crypto import audit


def test_log_sign_emits_structured_event() -> None:
    with capture_logs() as cap:
        audit.log_sign("ed25519", "kid", "ab" * 32, success=True, duration_ms=1.25)
    assert cap
    assert cap[0]["event"] == "crypto.sign"
    assert cap[0]["algorithm"] == "ed25519"
    assert cap[0]["message_hash_prefix"] == "abababababababab"


def test_log_verify_and_encrypt() -> None:
    with capture_logs() as cap:
        audit.log_verify("ed25519", "kid", success=False, duration_ms=2.0)
        audit.log_encrypt("kf", 100, success=True)
        audit.log_key_event("rotate", "k1", "ed25519", reason="policy")
        audit.log_tsa_attempt("FreeTSA", success=True, status="granted", duration_ms=10.0)
    events = {c["event"] for c in cap}
    assert "crypto.verify" in events
    assert "crypto.encrypt" in events
    assert "crypto.key.rotate" in events
    assert "crypto.timestamp" in events
