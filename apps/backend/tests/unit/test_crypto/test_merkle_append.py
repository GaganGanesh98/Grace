"""Unit tests for append-only SHA-256 MerkleTree."""

from __future__ import annotations

import hashlib

import pytest

from axiom.services.crypto.merkle import MerkleTree


def _leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def test_empty_tree() -> None:
    t = MerkleTree()
    assert t.get_root() == hashlib.sha256(b"").digest()
    with pytest.raises(ValueError, match="empty"):
        t.get_proof(0)


def test_single_leaf() -> None:
    t = MerkleTree()
    idx = t.add_leaf(b"only")
    assert idx == 0
    lh = _leaf_hash(b"only")
    root = t.get_root()
    assert root == lh
    proof = t.get_proof(0)
    assert MerkleTree.verify_proof(lh, proof, root) is True


def test_multiple_leaves_and_proof() -> None:
    t = MerkleTree()
    data = [b"a", b"b", b"c"]
    for d in data:
        t.add_leaf(d)
    root = t.get_root()
    for i, d in enumerate(data):
        lh = _leaf_hash(d)
        proof = t.get_proof(i)
        assert MerkleTree.verify_proof(lh, proof, root) is True


def test_tampered_leaf_fails() -> None:
    t = MerkleTree()
    t.add_leaf(b"x")
    root = t.get_root()
    proof = t.get_proof(0)
    bad_leaf = _leaf_hash(b"y")
    assert MerkleTree.verify_proof(bad_leaf, proof, root) is False


def test_wrong_root_fails() -> None:
    t = MerkleTree()
    t.add_leaf(b"z")
    proof = t.get_proof(0)
    lh = _leaf_hash(b"z")
    wrong = hashlib.sha256(b"not-the-root").digest()
    assert MerkleTree.verify_proof(lh, proof, wrong) is False
