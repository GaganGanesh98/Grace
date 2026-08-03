"""RFC 6962 Merkle audit trees (SHA-256, domain-separated leaf and interior nodes)."""

from __future__ import annotations

import hashlib
import hmac
import struct
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from ._util import constant_time_compare, validate_bytes
from .exceptions import CryptoInputError

__all__ = [
    "ConsistencyProof",
    "InclusionProof",
    "MerkleSnapshot",
    "MerkleTree",
    "build_tree",
    "consistency_proof",
    "inclusion_proof",
    "verify_consistency",
    "verify_inclusion",
]

_LEAF_PREFIX = b"\x00"
_INTERIOR_PREFIX = b"\x01"


def _leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(_LEAF_PREFIX + data).digest()


def _internal_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(_INTERIOR_PREFIX + left + right).digest()


def _largest_pow2_lt(n: int) -> int:
    if n <= 1:
        msg = "internal: n must be > 1"
        raise ValueError(msg)
    return int(2 ** ((n - 1).bit_length() - 1))


def _mth(leaves: tuple[bytes, ...]) -> bytes:
    """RFC 6962 Merkle Tree Hash MTH(D[0:n])."""
    n = len(leaves)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return _leaf_hash(leaves[0])
    k = _largest_pow2_lt(n)
    return _internal_hash(_mth(leaves[:k]), _mth(leaves[k:]))


def _audit_path(leaf_index: int, leaves: tuple[bytes, ...]) -> tuple[bytes, ...]:
    n = len(leaves)
    if not 0 <= leaf_index < n:
        msg = "leaf_index out of range"
        raise IndexError(msg)
    if n == 1:
        return ()
    k = _largest_pow2_lt(n)
    if leaf_index < k:
        sub = list(_audit_path(leaf_index, leaves[:k]))
        sub.append(_mth(leaves[k:]))
        return tuple(sub)
    sub = list(_audit_path(leaf_index - k, leaves[k:]))
    sub.append(_mth(leaves[:k]))
    return tuple(sub)


def _root_from_audit_path(
    leaf_hash: bytes,
    leaf_index: int,
    tree_size: int,
    audit_path: deque[bytes],
) -> bytes:
    """RFC 6962 Merkle audit path verification (Certificate Transparency style)."""
    calculated_hash = leaf_hash
    node_index = leaf_index
    last_node = tree_size - 1
    while last_node > 0:
        if not audit_path:
            return b""  # proof too short — mismatch root
        if node_index % 2:
            audit_hash = audit_path.popleft()
            calculated_hash = _internal_hash(audit_hash, calculated_hash)
        elif node_index < last_node:
            audit_hash = audit_path.popleft()
            calculated_hash = _internal_hash(calculated_hash, audit_hash)
        node_index //= 2
        last_node //= 2
    if audit_path:
        return b""  # proof too long — root mismatch
    return calculated_hash


def _subproof(m: int, leaves: tuple[bytes, ...], *, for_original: bool) -> list[bytes]:
    """RFC 6962 SUBPROOF for consistency (internal)."""
    n = len(leaves)
    if m == n:
        return [] if for_original else [_mth(leaves)]
    k = _largest_pow2_lt(n)
    if m <= k:
        return [*_subproof(m, leaves[:k], for_original=for_original), _mth(leaves[k:])]
    return [*_subproof(m - k, leaves[k:], for_original=False), _mth(leaves[:k])]


def _verify_consistency_proof(
    old_root: bytes,
    new_root: bytes,
    old_size: int,
    new_size: int,
    proof: tuple[bytes, ...],
) -> bool:
    """Port of RFC 6962 / CT consistency verification."""
    if old_size < 0 or new_size < 0:
        return False
    if old_size > new_size:
        return False
    if old_size == new_size:
        if len(old_root) != 32 or len(new_root) != 32:
            return False
        return constant_time_compare(old_root, new_root)
    if old_size == 0:
        return True

    node = old_size - 1
    last_node = new_size - 1
    p = deque(proof)

    while node % 2 == 1:
        node //= 2
        last_node //= 2

    try:
        if node != 0:
            new_hash = old_hash = p.popleft()
        else:
            new_hash = old_hash = old_root

        while node != 0:
            if node % 2:
                next_node = p.popleft()
                old_hash = _internal_hash(next_node, old_hash)
                new_hash = _internal_hash(next_node, new_hash)
            elif node < last_node:
                new_hash = _internal_hash(new_hash, p.popleft())
            node //= 2
            last_node //= 2

        while last_node != 0:
            new_hash = _internal_hash(new_hash, p.popleft())
            last_node //= 2

    except IndexError:
        return False

    if p:
        return False

    return (
        len(new_root) == 32
        and constant_time_compare(new_hash, new_root)
        and len(old_root) == 32
        and constant_time_compare(old_hash, old_root)
    )


def _leaf_prefix_equal(old: tuple[bytes, ...], new_prefix: tuple[bytes, ...]) -> bool:
    if len(old) != len(new_prefix):
        return False
    for a, b in zip(old, new_prefix, strict=True):
        if len(a) != len(b):
            return False
        if not constant_time_compare(a, b):
            return False
    return True


@dataclass(frozen=True)
class MerkleSnapshot:
    leaves: tuple[bytes, ...]
    root: bytes
    size: int


@dataclass(frozen=True)
class InclusionProof:
    leaf_index: int
    tree_size: int
    path: tuple[bytes, ...]


@dataclass(frozen=True)
class ConsistencyProof:
    old_size: int
    new_size: int
    path: tuple[bytes, ...]


def build_tree(leaves: Sequence[bytes]) -> MerkleSnapshot:
    validated: list[bytes] = []
    for i, leaf in enumerate(leaves):
        validated.append(validate_bytes(leaf, f"leaves[{i}]", min_len=1))
    tup = tuple(validated)
    root = _mth(tup)
    return MerkleSnapshot(leaves=tup, root=root, size=len(tup))


def inclusion_proof(tree: MerkleSnapshot, leaf_index: int) -> InclusionProof:
    if tree.size == 0:
        msg = "cannot build inclusion proof for an empty tree"
        raise ValueError(msg)
    path = _audit_path(leaf_index, tree.leaves)
    return InclusionProof(leaf_index=leaf_index, tree_size=tree.size, path=path)


def verify_inclusion(root: bytes, leaf: bytes, proof: InclusionProof) -> bool:
    validate_bytes(root, "root", exact_len=32)
    validate_bytes(leaf, "leaf", min_len=1)
    if proof.tree_size <= 0 or not (0 <= proof.leaf_index < proof.tree_size):
        return False
    leaf_hash = _leaf_hash(leaf)
    calc = _root_from_audit_path(leaf_hash, proof.leaf_index, proof.tree_size, deque(proof.path))
    return len(calc) == 32 and hmac.compare_digest(calc, root)


def consistency_proof(old_tree: MerkleSnapshot, new_tree: MerkleSnapshot) -> ConsistencyProof:
    m = old_tree.size
    n = new_tree.size
    if m > n:
        msg = "old tree cannot be larger than new tree"
        raise ValueError(msg)
    if not _leaf_prefix_equal(old_tree.leaves, new_tree.leaves[:m]):
        msg = "new tree leaves must begin with the old tree's leaves"
        raise ValueError(msg)
    if m == n:
        return ConsistencyProof(old_size=m, new_size=n, path=())
    if m == 0:
        return ConsistencyProof(old_size=0, new_size=n, path=())
    path = tuple(_subproof(m, new_tree.leaves, for_original=True))
    return ConsistencyProof(old_size=m, new_size=n, path=path)


def verify_consistency(old_root: bytes, new_root: bytes, proof: ConsistencyProof) -> bool:
    validate_bytes(old_root, "old_root", exact_len=32)
    validate_bytes(new_root, "new_root", exact_len=32)
    return _verify_consistency_proof(old_root, new_root, proof.old_size, proof.new_size, proof.path)


def _append_leaf_digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _append_build_levels(leaf_data: list[bytes]) -> list[list[bytes]]:
    if not leaf_data:
        return []
    levels: list[list[bytes]] = []
    cur = [_append_leaf_digest(d) for d in leaf_data]
    levels.append(cur)
    while len(cur) > 1:
        nxt: list[bytes] = []
        for i in range(0, len(cur), 2):
            if i + 1 < len(cur):
                nxt.append(hashlib.sha256(cur[i] + cur[i + 1]).digest())
            else:
                nxt.append(hashlib.sha256(cur[i] + cur[i]).digest())
        cur = nxt
        levels.append(cur)
    return levels


def _append_sibling_at_level(level: list[bytes], idx: int) -> bytes:
    m = len(level)
    if idx % 2:
        return level[idx - 1]
    if idx + 1 < m:
        return level[idx + 1]
    return level[idx]


class MerkleTree:
    """Append-only Merkle tree: SHA-256 leaves, paired interior nodes, odd level duplicates last."""

    _PROOF_MAGIC = b"AX75"
    _SERIAL_MAGIC = b"AXMT"
    _SERIAL_VERSION = 1

    def __init__(self, *, serialized_root: bytes | None = None) -> None:
        self._leaves: list[bytes] = []
        self._serialized_root = serialized_root

    def serialize(self) -> bytes:
        """Serialize tree state; includes root commitment for integrity checks."""
        root = self.get_root()
        parts = [
            self._SERIAL_MAGIC,
            bytes([self._SERIAL_VERSION]),
            root,
            struct.pack(">I", len(self._leaves)),
        ]
        for leaf in self._leaves:
            parts.append(struct.pack(">I", len(leaf)))
            parts.append(leaf)
        return b"".join(parts)

    @classmethod
    def deserialize(cls, data: bytes) -> MerkleTree:
        """Reconstruct a :class:`MerkleTree` from :meth:`serialize` output."""
        validate_bytes(data, "data", min_len=41)
        if data[:4] != cls._SERIAL_MAGIC:
            raise CryptoInputError("invalid Merkle serialization magic")
        if data[4] != cls._SERIAL_VERSION:
            msg = f"unsupported Merkle serialization version: {data[4]}"
            raise CryptoInputError(msg)
        root = bytes(data[5:37])
        (n_leaves,) = struct.unpack(">I", data[37:41])
        offset = 41
        leaves: list[bytes] = []
        for _ in range(n_leaves):
            if offset + 4 > len(data):
                raise CryptoInputError("truncated Merkle leaf length prefix")
            (ln,) = struct.unpack(">I", data[offset : offset + 4])
            offset += 4
            if offset + ln > len(data):
                raise CryptoInputError("truncated Merkle leaf bytes")
            leaves.append(bytes(data[offset : offset + ln]))
            offset += ln
        if offset != len(data):
            raise CryptoInputError("trailing bytes in Merkle serialization")
        tree = cls(serialized_root=root)
        tree._leaves = leaves
        return tree

    def verify_integrity(self) -> bool:
        """Recompute the root from leaves and compare to the committed root when present."""
        if self._serialized_root is None:
            return True
        if len(self._serialized_root) != 32:
            return False
        return hmac.compare_digest(self.get_root(), self._serialized_root)

    def add_leaf(self, data: bytes) -> int:
        validate_bytes(data, "data", min_len=1)
        self._leaves.append(data)
        return len(self._leaves) - 1

    def get_root(self) -> bytes:
        levels = _append_build_levels(self._leaves)
        if not levels:
            return hashlib.sha256(b"").digest()
        return levels[-1][0]

    def get_proof(self, leaf_index: int) -> list[bytes]:
        if not self._leaves:
            msg = "cannot build proof for an empty tree"
            raise ValueError(msg)
        if not 0 <= leaf_index < len(self._leaves):
            msg = "leaf_index out of range"
            raise IndexError(msg)
        levels = _append_build_levels(self._leaves)
        n = len(self._leaves)
        proof: list[bytes] = [self._PROOF_MAGIC + struct.pack(">II", leaf_index, n)]
        idx = leaf_index
        for level in levels[:-1]:
            proof.append(_append_sibling_at_level(level, idx))
            idx //= 2
        return proof

    @staticmethod
    def verify_proof(leaf_hash: bytes, proof: list[bytes], root: bytes) -> bool:
        validate_bytes(leaf_hash, "leaf_hash", exact_len=32)
        validate_bytes(root, "root", exact_len=32)
        if not isinstance(proof, list):
            raise CryptoInputError("proof must be a list")
        if not proof or len(proof[0]) < 12:
            return False
        if not constant_time_compare(proof[0][:4], MerkleTree._PROOF_MAGIC):
            return False
        leaf_index, num_leaves = struct.unpack(">II", proof[0][4:12])
        siblings = proof[1:]
        cur = leaf_hash
        m = num_leaves
        idx = leaf_index
        for sib in siblings:
            if len(sib) != 32:
                return False
            if idx % 2:
                cur = hashlib.sha256(sib + cur).digest()
            elif idx + 1 < m:
                cur = hashlib.sha256(cur + sib).digest()
            else:
                cur = hashlib.sha256(cur + sib).digest()
            idx //= 2
            m = (m + 1) // 2
        return m == 1 and hmac.compare_digest(cur, root)
