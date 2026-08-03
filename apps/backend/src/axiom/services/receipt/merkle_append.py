"""Atomic, per-project Merkle append with inclusion-proof generation.

Concurrency model
-----------------
Two concurrent ``POST /v1/govern`` for the SAME project must get distinct
``leaf_index`` values (0, 1, 2, ...) and each of their inclusion proofs must
verify against the tree at its time-of-append. Two concurrent calls for
DIFFERENT projects must proceed in parallel.

We achieve this with a Postgres transaction-scoped advisory lock keyed on a
64-bit hash of ``"axiom:merkle:<project_id>"``. The lock is automatically
released at ``COMMIT`` or ``ROLLBACK``. Because the outer request uses a
single ``AsyncSession`` with transactional DDL, ``append`` + ``persist_leaf``
+ the Execution/Receipt INSERTs all land in the same transaction and obey
the same lock.

Phase 2 rebuilds the entire Merkle tree on every append (O(n)). For N <= ~50k
leaves per project on local hardware this finishes in well under 100ms. Phase
5 will optimize with cached subroots; leaving that for later is a deliberate
simplicity choice.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.merkle_node import MerkleNode
from axiom.services.crypto.merkle import (
    InclusionProof,
    build_tree,
    inclusion_proof,
)

_ADVISORY_LOCK_NAMESPACE = "axiom:merkle:"


def _advisory_key(project_id: UUID) -> int:
    """64-bit signed integer key for ``pg_advisory_xact_lock``.

    Postgres advisory lock keys are ``bigint``. We hash a namespaced project
    string to stay well clear of collisions with other subsystems.
    """

    digest = hashlib.blake2b(
        f"{_ADVISORY_LOCK_NAMESPACE}{project_id}".encode(),
        digest_size=8,
    ).digest()
    value = int.from_bytes(digest, "big", signed=False)
    if value >= 2**63:
        value -= 2**64
    return value


class MerkleAppender:
    """Append + proof generator. Stateless; safe to reuse across requests.

    Invariant: ``merkle_nodes.leaf_hash`` stores the RAW payload-hash (the
    same 32-byte value the Evidence stage produced). The RFC 6962 leaf
    domain-separation byte (``0x00``) is applied by the crypto.merkle layer
    when the tree is (re)built; we never store pre-hashed leaves.
    """

    async def append(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        receipt_id: str,
        payload_hash: bytes,
    ) -> tuple[int, bytes, int, tuple[bytes, ...]]:
        """Reserve a leaf index for this project + build the new root + proof.

        The row is NOT inserted here (Receipt stage owns the inserts so the
        whole transaction is atomic). Call ``persist_leaf`` after a successful
        signature.

        Returns: (leaf_index, root, tree_size, audit_path).
        """

        _ = receipt_id  # reserved for future auditing hooks
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _advisory_key(project_id)},
        )

        existing_rows = await session.scalars(
            select(MerkleNode.leaf_hash)
            .where(MerkleNode.project_id == project_id)
            .order_by(MerkleNode.leaf_index.asc())
        )
        existing = list(existing_rows)

        new_leaves: list[bytes] = [*existing, payload_hash]
        tree = build_tree(new_leaves)
        leaf_index = tree.size - 1
        proof: InclusionProof = inclusion_proof(tree, leaf_index)
        return leaf_index, tree.root, tree.size, proof.path

    async def persist_leaf(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        leaf_index: int,
        leaf_hash: bytes,
        receipt_id: str,
    ) -> None:
        """Insert the MerkleNode row within the caller's transaction."""

        session.add(
            MerkleNode(
                project_id=project_id,
                leaf_index=leaf_index,
                leaf_hash=leaf_hash,
                receipt_id=receipt_id,
            )
        )

    async def rebuild_tree(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        up_to_size: int | None = None,
    ) -> tuple[bytes, ...]:
        """Return the ordered leaf-payload list for this project (all or the
        first ``up_to_size`` leaves).

        Used by ``/v1/verify`` to re-compute the tree that was present when a
        specific receipt was appended.
        """

        query = (
            select(MerkleNode.leaf_hash)
            .where(MerkleNode.project_id == project_id)
            .order_by(MerkleNode.leaf_index.asc())
        )
        if up_to_size is not None:
            query = query.limit(up_to_size)
        rows = await session.scalars(query)
        return tuple(rows)
