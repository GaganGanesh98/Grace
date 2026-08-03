"""Merkle append-only tree serialization and integrity."""

from __future__ import annotations

from axiom.services.crypto.merkle import MerkleTree


def test_serialize_round_trip_hundred_leaves() -> None:
    t = MerkleTree()
    for i in range(100):
        t.add_leaf(f"leaf-{i}".encode())
    raw = t.serialize()
    t2 = MerkleTree.deserialize(raw)
    assert t2.verify_integrity() is True
    assert t.get_root() == t2.get_root()


def test_tampered_serialization_fails_integrity() -> None:
    t = MerkleTree()
    for i in range(100):
        t.add_leaf(f"leaf-{i}".encode())
    raw = bytearray(t.serialize())
    raw[10] ^= 0x01
    t2 = MerkleTree.deserialize(bytes(raw))
    assert t2.verify_integrity() is False
