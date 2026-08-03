"""Tests for RFC 6962 Merkle trees."""

from __future__ import annotations

import hashlib

import pytest

from axiom.services.crypto import merkle


def test_empty_tree() -> None:
    t = merkle.build_tree([])
    assert t.size == 0
    assert t.root == hashlib.sha256(b"").digest()


def test_single_leaf() -> None:
    leaf = b"hello"
    t = merkle.build_tree([leaf])
    lh = hashlib.sha256(b"\x00" + leaf).digest()
    assert t.root == lh


def test_two_leaves() -> None:
    a, b = b"a", b"b"
    t = merkle.build_tree([a, b])
    la = hashlib.sha256(b"\x00" + a).digest()
    lb = hashlib.sha256(b"\x00" + b).digest()
    expect = hashlib.sha256(b"\x01" + la + lb).digest()
    assert t.root == expect


def test_odd_leaves() -> None:
    leaves = [b"a", b"b", b"c"]
    t = merkle.build_tree(leaves)
    assert t.size == 3
    assert len(t.root) == 32


def test_inclusion_proof_verifies() -> None:
    leaves = [b"x", b"y", b"z"]
    tree = merkle.build_tree(leaves)
    for i in range(3):
        proof = merkle.inclusion_proof(tree, i)
        assert merkle.verify_inclusion(tree.root, leaves[i], proof) is True


def test_inclusion_proof_rejects_wrong_leaf() -> None:
    tree = merkle.build_tree([b"a", b"b"])
    proof = merkle.inclusion_proof(tree, 0)
    assert merkle.verify_inclusion(tree.root, b"tampered", proof) is False


def test_inclusion_proof_rejects_wrong_index() -> None:
    tree = merkle.build_tree([b"a", b"b"])
    proof = merkle.inclusion_proof(tree, 0)
    bad = merkle.InclusionProof(leaf_index=1, tree_size=proof.tree_size, path=proof.path)
    assert merkle.verify_inclusion(tree.root, b"a", bad) is False


def test_consistency_proof_verifies() -> None:
    old = merkle.build_tree([b"a", b"b"])
    new = merkle.build_tree([b"a", b"b", b"c", b"d"])
    p = merkle.consistency_proof(old, new)
    assert merkle.verify_consistency(old.root, new.root, p) is True


def test_consistency_proof_rejects_inconsistent_trees() -> None:
    t1 = merkle.build_tree([b"a"])
    t2 = merkle.build_tree([b"b"])
    with pytest.raises(ValueError):
        merkle.consistency_proof(t1, t2)


def test_inclusion_proof_empty_tree_raises() -> None:
    tree = merkle.build_tree([])
    with pytest.raises(ValueError):
        merkle.inclusion_proof(tree, 0)


def test_domain_separation_changes_root(monkeypatch: pytest.MonkeyPatch) -> None:
    leaves = [b"a", b"b", b"c"]
    good = merkle.build_tree(leaves)
    proof = merkle.inclusion_proof(good, 1)
    monkeypatch.setattr(merkle, "_LEAF_PREFIX", b"")
    bad = merkle.build_tree(leaves)
    assert good.root != bad.root
    assert merkle.verify_inclusion(good.root, leaves[1], proof) is False
