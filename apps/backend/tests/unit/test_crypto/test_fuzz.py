"""Fuzz testing for crypto modules using Hypothesis."""

from __future__ import annotations

import hashlib
import os

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from axiom.services.crypto import ed25519, hybrid, ml_dsa_65, vault
from axiom.services.crypto.merkle import MerkleTree


@given(message=st.binary(min_size=1, max_size=10000))
@settings(max_examples=500)
def test_ed25519_sign_verify_roundtrip(message: bytes) -> None:
    priv, pub = ed25519.generate_keypair(raw=True)
    sig = ed25519.sign(message, priv)
    assert ed25519.verify(message, sig, pub) is True


@given(message=st.binary(min_size=1, max_size=10000), tamper_pos=st.integers(min_value=0))
@settings(max_examples=500)
def test_ed25519_tampered_message_fails(message: bytes, tamper_pos: int) -> None:
    assume(len(message) > 0)
    tamper_pos %= len(message)
    priv, pub = ed25519.generate_keypair(raw=True)
    sig = ed25519.sign(message, priv)
    tampered = bytearray(message)
    tampered[tamper_pos] ^= 0xFF
    assert ed25519.verify(bytes(tampered), sig, pub) is False


@given(leaves=st.lists(st.binary(min_size=1, max_size=1000), min_size=1, max_size=100))
@settings(max_examples=200)
def test_merkle_proof_always_verifies(leaves: list[bytes]) -> None:
    tree = MerkleTree()
    for leaf in leaves:
        tree.add_leaf(leaf)
    root = tree.get_root()
    for i in range(len(leaves)):
        proof = tree.get_proof(i)
        leaf_hash = hashlib.sha256(leaves[i]).digest()
        assert MerkleTree.verify_proof(leaf_hash, proof, root) is True


@given(leaves=st.lists(st.binary(min_size=1, max_size=1000), min_size=2, max_size=50))
@settings(max_examples=200)
def test_merkle_tampered_leaf_fails(leaves: list[bytes]) -> None:
    tree = MerkleTree()
    for leaf in leaves:
        tree.add_leaf(leaf)
    root = tree.get_root()
    fake_hash = hashlib.sha256(b"TAMPERED").digest()
    proof = tree.get_proof(0)
    assert MerkleTree.verify_proof(fake_hash, proof, root) is False


@given(plaintext=st.binary(min_size=1, max_size=10000))
@settings(max_examples=500)
def test_vault_encrypt_decrypt_roundtrip(plaintext: bytes) -> None:
    key = os.urandom(32)
    ciphertext = vault.encrypt(plaintext, key)
    assert vault.decrypt(ciphertext, key) == plaintext


@given(plaintext=st.binary(min_size=1, max_size=1000))
@settings(max_examples=200)
def test_vault_wrong_key_fails(plaintext: bytes) -> None:
    key1 = os.urandom(32)
    key2 = os.urandom(32)
    assume(key1 != key2)
    ciphertext = vault.encrypt(plaintext, key1)
    with pytest.raises(vault.DecryptionError):
        vault.decrypt(ciphertext, key2)


@given(message=st.binary(min_size=1, max_size=5000))
@settings(max_examples=300)
def test_hybrid_sign_verify_roundtrip(message: bytes) -> None:
    ed_priv, ed_pub = ed25519.generate_keypair(raw=True)
    if ml_dsa_65.ML_DSA_AVAILABLE:
        ml_priv, ml_pub = ml_dsa_65.generate_keypair()
    else:
        ml_priv = b"\x00" * 32
        ml_pub = b"\x00" * 32
    sig = hybrid.hybrid_sign(message, ed_priv, ml_priv)
    assert hybrid.hybrid_verify(message, sig, ed_pub, ml_pub) is True
