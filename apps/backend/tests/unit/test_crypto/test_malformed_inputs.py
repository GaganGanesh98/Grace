"""Malicious or malformed inputs must raise CryptoError subclasses, never crash."""

from __future__ import annotations

import pytest

from axiom.services.crypto import ed25519, hybrid, ml_dsa_65, vault
from axiom.services.crypto.exceptions import AlgorithmNotFoundError, CryptoError, CryptoInputError
from axiom.services.crypto.hybrid import HybridSignature
from axiom.services.crypto.merkle import MerkleTree
from axiom.services.crypto.registry import AlgorithmRegistry

GARBAGE_INPUTS = [
    None,
    "",
    0,
    -1,
    3.14,
    True,
    [],
    {},
    b"",
    b"\x00" * 1,
    b"\xff" * 10000,
    "not bytes",
    object(),
]

# Single non-empty bytes are valid Merkle leaves; only reject ill-typed / empty inputs here.
ADD_LEAF_BAD_INPUTS = [
    None,
    "",
    0,
    -1,
    3.14,
    True,
    [],
    {},
    b"",
    "not bytes",
    object(),
]


@pytest.mark.parametrize("garbage", GARBAGE_INPUTS)
def test_ed25519_sign_rejects_garbage_private_key(garbage: object) -> None:
    with pytest.raises(CryptoError):
        ed25519.sign(b"hello", garbage)  # type: ignore[arg-type]


@pytest.mark.parametrize("garbage", GARBAGE_INPUTS)
def test_ed25519_verify_rejects_garbage_signature(garbage: object) -> None:
    _, pub = ed25519.generate_keypair(raw=True)
    with pytest.raises(CryptoError):
        ed25519.verify(b"hello", garbage, pub)  # type: ignore[arg-type]


@pytest.mark.parametrize("garbage", GARBAGE_INPUTS)
def test_ed25519_verify_rejects_garbage_public_key(garbage: object) -> None:
    priv, _pub = ed25519.generate_keypair(raw=True)
    sig = ed25519.sign(b"hello", priv)
    with pytest.raises(CryptoError):
        ed25519.verify(b"hello", sig, garbage)  # type: ignore[arg-type]


@pytest.mark.parametrize("garbage", ADD_LEAF_BAD_INPUTS)
def test_merkle_add_leaf_rejects_garbage(garbage: object) -> None:
    t = MerkleTree()
    with pytest.raises(CryptoError):
        t.add_leaf(garbage)  # type: ignore[arg-type]


@pytest.mark.parametrize("garbage", GARBAGE_INPUTS)
def test_vault_encrypt_rejects_garbage_key(garbage: object) -> None:
    with pytest.raises(CryptoError):
        vault.encrypt(b"hello", garbage)  # type: ignore[arg-type]


@pytest.mark.parametrize("garbage", GARBAGE_INPUTS)
def test_vault_decrypt_rejects_garbage_key(garbage: object) -> None:
    with pytest.raises(CryptoError):
        vault.decrypt(b"\x00" * 40, garbage)  # type: ignore[arg-type]


@pytest.mark.parametrize("garbage", GARBAGE_INPUTS)
def test_vault_decrypt_rejects_garbage_ciphertext(garbage: object) -> None:
    with pytest.raises(CryptoError):
        vault.decrypt(garbage, b"k" * 32)  # type: ignore[arg-type]


def test_hybrid_sign_rejects_garbage_ed25519_key() -> None:
    with pytest.raises(CryptoError):
        hybrid.hybrid_sign(b"msg", object(), b"\x00" * 32)  # type: ignore[arg-type]


def test_hybrid_sign_rejects_garbage_ml_key() -> None:
    with pytest.raises(CryptoError):
        hybrid.hybrid_sign(b"msg", b"\x00" * 32, object())  # type: ignore[arg-type]


def test_registry_rejects_unknown_algorithm() -> None:
    r = AlgorithmRegistry()
    with pytest.raises(AlgorithmNotFoundError):
        r.get_signer("no-such-algorithm")


@pytest.mark.parametrize("garbage", [None, 0, [], b"", object()])
def test_registry_rejects_bad_algorithm_name(garbage: object) -> None:
    r = AlgorithmRegistry()
    with pytest.raises(CryptoInputError):
        r.get_signer(garbage)  # type: ignore[arg-type]


def test_ml_dsa_sign_rejects_garbage_key() -> None:
    if not ml_dsa_65.ML_DSA_AVAILABLE:
        pytest.skip("ML-DSA not available")
    with pytest.raises(CryptoError):
        ml_dsa_65.sign(b"hello", b"short")


def test_ml_dsa_verify_rejects_garbage() -> None:
    with pytest.raises(CryptoError):
        ml_dsa_65.verify(b"m", b"sig", b"pk")


def test_merkle_verify_proof_rejects_garbage_proof_type() -> None:
    with pytest.raises(CryptoError):
        MerkleTree.verify_proof(b"\x00" * 32, object(), b"\x00" * 32)  # type: ignore[arg-type]


def test_verify_inclusion_rejects_bad_root_len() -> None:
    from axiom.services.crypto import merkle

    tree = merkle.build_tree([b"x"])
    proof = merkle.inclusion_proof(tree, 0)
    with pytest.raises(CryptoError):
        merkle.verify_inclusion(b"short", b"x", proof)


def test_build_tree_rejects_empty_leaf() -> None:
    from axiom.services.crypto import merkle

    with pytest.raises(CryptoError):
        merkle.build_tree([b""])


def test_hybrid_verify_rejects_bad_ed25519_sig_len() -> None:
    esk, epk = ed25519.generate_keypair(raw=True)
    if ml_dsa_65.ML_DSA_AVAILABLE:
        msk, mpk = ml_dsa_65.generate_keypair()
    else:
        msk = b"\x00" * 32
        mpk = b"\x00" * 32
    sig = hybrid.hybrid_sign(b"msg", esk, msk)
    bad = HybridSignature(ed25519_sig=sig.ed25519_sig[:10], ml_dsa_sig=sig.ml_dsa_sig)
    with pytest.raises(CryptoError):
        hybrid.hybrid_verify(b"msg", bad, epk, mpk)


def test_stable_key_id_rejects_non_string() -> None:
    with pytest.raises(CryptoError):
        ed25519.stable_key_id(object())  # type: ignore[arg-type]


def test_consistency_proof_snapshot_types() -> None:
    from axiom.services.crypto import merkle

    a = merkle.build_tree([b"x"])
    b_ = merkle.build_tree([b"y"])
    with pytest.raises(ValueError):
        merkle.consistency_proof(a, b_)
