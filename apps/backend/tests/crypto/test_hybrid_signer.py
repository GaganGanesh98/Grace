"""Tests for hybrid Ed25519 + ML-DSA signing."""

from __future__ import annotations

from axiom.services.crypto import ed25519, hybrid_signer, ml_dsa


def _keys() -> tuple[ed25519.Ed25519KeyPair, ml_dsa.MLDSAKeyPair]:
    return ed25519.generate_keypair(), ml_dsa.generate_keypair()


def test_sign_verify_round_trip() -> None:
    ek, mk = _keys()
    payload = {"msg": "hi"}
    sig = hybrid_signer.sign_hybrid(
        payload,
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    assert hybrid_signer.verify_hybrid(sig, ek.public_key_pem, mk.public_key_bytes, payload) is True


def test_verify_rejects_ed25519_tamper() -> None:
    ek, mk = _keys()
    sig = hybrid_signer.sign_hybrid(
        {"a": 1},
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    bad = hybrid_signer.HybridSignature(
        payload_bytes=sig.payload_bytes,
        payload_hash=sig.payload_hash,
        ed25519_signature=sig.ed25519_signature[:-1] + bytes([sig.ed25519_signature[-1] ^ 1]),
        ed25519_key_id=sig.ed25519_key_id,
        ml_dsa_signature=sig.ml_dsa_signature,
        ml_dsa_key_id=sig.ml_dsa_key_id,
    )
    assert (
        hybrid_signer.verify_hybrid(
            bad,
            ek.public_key_pem,
            mk.public_key_bytes,
            {"a": 1},
        )
        is False
    )


def test_verify_rejects_mldsa_tamper() -> None:
    ek, mk = _keys()
    sig = hybrid_signer.sign_hybrid(
        {"a": 1},
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    bad = hybrid_signer.HybridSignature(
        payload_bytes=sig.payload_bytes,
        payload_hash=sig.payload_hash,
        ed25519_signature=sig.ed25519_signature,
        ed25519_key_id=sig.ed25519_key_id,
        ml_dsa_signature=sig.ml_dsa_signature[:-1] + bytes([sig.ml_dsa_signature[-1] ^ 1]),
        ml_dsa_key_id=sig.ml_dsa_key_id,
    )
    assert (
        hybrid_signer.verify_hybrid(
            bad,
            ek.public_key_pem,
            mk.public_key_bytes,
            {"a": 1},
        )
        is False
    )


def test_verify_rejects_payload_mismatch() -> None:
    ek, mk = _keys()
    sig = hybrid_signer.sign_hybrid(
        {"a": 1},
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    assert (
        hybrid_signer.verify_hybrid(
            sig,
            ek.public_key_pem,
            mk.public_key_bytes,
            {"a": 2},
        )
        is False
    )


def test_verify_rejects_key_mismatch() -> None:
    ek, mk = _keys()
    ek2, _ = _keys()
    sig = hybrid_signer.sign_hybrid(
        {"a": 1},
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    assert (
        hybrid_signer.verify_hybrid(
            sig,
            ek2.public_key_pem,
            mk.public_key_bytes,
            {"a": 1},
        )
        is False
    )


def test_canonical_payload_used() -> None:
    ek, mk = _keys()
    s1 = hybrid_signer.sign_hybrid(
        {"a": 1, "b": 2},
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    s2 = hybrid_signer.sign_hybrid(
        {"b": 2, "a": 1},
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    assert s1.payload_bytes == s2.payload_bytes
    assert s1.ed25519_signature == s2.ed25519_signature
    assert s1.ml_dsa_key_id == s2.ml_dsa_key_id
    assert (
        hybrid_signer.verify_hybrid(
            s1,
            ek.public_key_pem,
            mk.public_key_bytes,
            {"a": 1, "b": 2},
        )
        is True
    )
    assert (
        hybrid_signer.verify_hybrid(
            s2,
            ek.public_key_pem,
            mk.public_key_bytes,
            {"b": 2, "a": 1},
        )
        is True
    )


def test_canonicalize_does_not_mutate_input() -> None:
    from axiom.services.crypto.canonical_json import canonicalize

    d = {"b": 1, "a": 2}
    canonicalize(d)
    assert list(d.keys()) == ["b", "a"]
