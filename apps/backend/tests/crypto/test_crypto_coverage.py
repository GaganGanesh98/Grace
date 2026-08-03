"""Targeted tests to satisfy crypto coverage gates."""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from axiom.services.crypto import canonical_json, ed25519, hybrid_signer, merkle, ml_dsa
from axiom.services.crypto.canonical_json import verify_canonical


def test_verify_canonical_invalid_utf8() -> None:
    assert verify_canonical(b"\xff\xfe") is False


def test_verify_canonical_invalid_json() -> None:
    assert verify_canonical(b"{") is False


def test_verify_canonical_noncanonical_bytes() -> None:
    assert verify_canonical(b"{ }") is False


def test_verify_canonical_noncanonicalizable(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_: object) -> bytes:
        raise canonical_json.NonCanonicalizableError("nope")

    monkeypatch.setattr(canonical_json, "canonicalize", boom)
    assert verify_canonical(b"[]") is False


def test_verify_canonical_typeerror(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_: object) -> bytes:
        raise TypeError("nope")

    monkeypatch.setattr(canonical_json, "canonicalize", boom)
    assert verify_canonical(b"[]") is False


def test_ed25519_verify_invalid_public_pem() -> None:
    assert ed25519.verify("not a pem", b"m", b"\x00" * 64) is False


def _ec_public_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


def test_ed25519_verify_non_ed25519_public_key() -> None:
    assert ed25519.verify(_ec_public_pem(), b"m", b"\x00" * 64) is False


def test_ed25519_stable_key_id_rejects_non_ed25519() -> None:
    from axiom.services.crypto.exceptions import CryptoInputError

    with pytest.raises(CryptoInputError):
        ed25519.stable_key_id(_ec_public_pem())


def test_ml_dsa_verify_exception_returns_false() -> None:
    assert ml_dsa.verify(b"short", b"m", b"x" * 3309) is False


def test_ed25519_verify_wrong_signature_length_raises() -> None:
    from axiom.services.crypto.exceptions import CryptoInputError

    kp = ed25519.generate_keypair()
    with pytest.raises(CryptoInputError):
        ed25519.verify(kp.public_key_pem, b"m", b"\x00" * 300)


def test_hybrid_verify_payload_mismatch() -> None:
    ek, mk = ed25519.generate_keypair(), ml_dsa.generate_keypair()
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


def test_hybrid_verify_ed25519_key_id_mismatch() -> None:
    ek, mk = ed25519.generate_keypair(), ml_dsa.generate_keypair()
    ek2 = ed25519.generate_keypair()
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


def test_hybrid_verify_ml_dsa_key_id_mismatch() -> None:
    ek, mk = ed25519.generate_keypair(), ml_dsa.generate_keypair()
    mk2 = ml_dsa.generate_keypair()
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
            mk2.public_key_bytes,
            {"a": 1},
        )
        is False
    )


def test_hybrid_verify_payload_digest_mismatch() -> None:
    ek, mk = ed25519.generate_keypair(), ml_dsa.generate_keypair()
    sig = hybrid_signer.sign_hybrid(
        {"a": 1},
        ek.private_key_pem,
        ek.public_key_pem,
        mk.private_key_bytes,
        mk.public_key_bytes,
    )
    bad = hybrid_signer.HybridSignature(
        payload_bytes=sig.payload_bytes,
        payload_hash=hashlib.sha256(b"other").digest(),
        ed25519_signature=sig.ed25519_signature,
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


def test_merkle_inclusion_proof_index_error() -> None:
    tree = merkle.build_tree([b"a"])
    with pytest.raises(IndexError):
        merkle.inclusion_proof(tree, 1)


def test_merkle_verify_inclusion_bad_bounds() -> None:
    tree = merkle.build_tree([b"a"])
    proof = merkle.inclusion_proof(tree, 0)
    bad = merkle.InclusionProof(leaf_index=0, tree_size=0, path=proof.path)
    assert merkle.verify_inclusion(tree.root, b"a", bad) is False
    bad2 = merkle.InclusionProof(leaf_index=1, tree_size=1, path=proof.path)
    assert merkle.verify_inclusion(tree.root, b"a", bad2) is False


def test_merkle_verify_inclusion_proof_too_short() -> None:
    tree = merkle.build_tree([b"a", b"b"])
    proof = merkle.inclusion_proof(tree, 0)
    short = merkle.InclusionProof(leaf_index=proof.leaf_index, tree_size=proof.tree_size, path=())
    assert merkle.verify_inclusion(tree.root, b"a", short) is False


def test_merkle_verify_inclusion_proof_too_long() -> None:
    tree = merkle.build_tree([b"a", b"b"])
    proof = merkle.inclusion_proof(tree, 0)
    long_path = (*proof.path, b"\x00" * 32)
    long_proof = merkle.InclusionProof(
        leaf_index=proof.leaf_index, tree_size=proof.tree_size, path=long_path
    )
    assert merkle.verify_inclusion(tree.root, b"a", long_proof) is False


def test_merkle_consistency_proof_prefix_mismatch() -> None:
    a = merkle.build_tree([b"x"])
    b_ = merkle.build_tree([b"y"])
    with pytest.raises(ValueError):
        merkle.consistency_proof(a, b_)


def test_merkle_verify_consistency_sizes() -> None:
    p = merkle.ConsistencyProof(old_size=-1, new_size=1, path=())
    assert merkle.verify_consistency(b"\x00" * 32, b"\x00" * 32, p) is False
    p2 = merkle.ConsistencyProof(old_size=2, new_size=1, path=())
    assert merkle.verify_consistency(b"\x00" * 32, b"\x00" * 32, p2) is False


def test_merkle_verify_consistency_same_size_roots_differ() -> None:
    t1 = merkle.build_tree([b"a"])
    t2 = merkle.build_tree([b"b"])
    p = merkle.ConsistencyProof(old_size=1, new_size=1, path=())
    assert merkle.verify_consistency(t1.root, t2.root, p) is False


def test_merkle_verify_consistency_same_size_match() -> None:
    t = merkle.build_tree([b"a"])
    p = merkle.ConsistencyProof(old_size=1, new_size=1, path=())
    assert merkle.verify_consistency(t.root, t.root, p) is True


def test_merkle_verify_consistency_empty_old() -> None:
    new = merkle.build_tree([b"a"])
    p = merkle.ConsistencyProof(old_size=0, new_size=1, path=(b"\x00" * 32,))
    assert merkle.verify_consistency(hashlib.sha256(b"").digest(), new.root, p) is True


def test_merkle_verify_consistency_bad_proof_short() -> None:
    old = merkle.build_tree([b"a", b"b"])
    new = merkle.build_tree([b"a", b"b", b"c"])
    p = merkle.ConsistencyProof(old_size=2, new_size=3, path=())
    assert merkle.verify_consistency(old.root, new.root, p) is False


def test_merkle_verify_consistency_bad_new_root() -> None:
    old = merkle.build_tree([b"a", b"b"])
    new = merkle.build_tree([b"a", b"b", b"c"])
    good = merkle.consistency_proof(old, new)
    bad = merkle.ConsistencyProof(old_size=good.old_size, new_size=good.new_size, path=good.path)
    assert merkle.verify_consistency(old.root, b"\x00" * 32, bad) is False


def test_merkle_verify_consistency_bad_old_root() -> None:
    old = merkle.build_tree([b"a", b"b"])
    new = merkle.build_tree([b"a", b"b", b"c"])
    good = merkle.consistency_proof(old, new)
    assert merkle.verify_consistency(b"\x00" * 32, new.root, good) is False


def test_merkle_verify_consistency_extra_proof_nodes() -> None:
    old = merkle.build_tree([b"a", b"b"])
    new = merkle.build_tree([b"a", b"b", b"c"])
    good = merkle.consistency_proof(old, new)
    junk = merkle.ConsistencyProof(
        old_size=good.old_size,
        new_size=good.new_size,
        path=(*good.path, b"\x00" * 32),
    )
    assert merkle.verify_consistency(old.root, new.root, junk) is False
