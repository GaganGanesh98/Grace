"""MerkleAppender tests: monotonic indices, per-project isolation, valid proofs."""

from __future__ import annotations

import asyncio
import secrets
from uuid import UUID

import pytest
from httpx import AsyncClient

from axiom.db import session_scope
from axiom.models.execution import Execution
from axiom.models.receipt import Receipt
from axiom.services.crypto.merkle import (
    InclusionProof,
    verify_inclusion,
)
from axiom.services.receipt.merkle_append import MerkleAppender
from tests.fixtures.governance import bootstrap_project_with_api_key


async def _seed_receipt(session, project_id: UUID, agent_id: UUID, payload_hash: bytes) -> str:
    receipt_id = "rcpt_" + secrets.token_urlsafe(12)
    execution_id = "exec_" + secrets.token_urlsafe(12)
    session.add(
        Execution(
            id=execution_id,
            project_id=project_id,
            agent_id=agent_id,
            policy_id="UNKNOWN",
            policy_version="0",
            action={"type": "test"},
            verdict="deny",
            rule_id=None,
            modification=None,
            escalation_target=None,
            reasoning="seed",
            mode="shadow",
            correlation_id="test",
        )
    )
    session.add(
        Receipt(
            id=receipt_id,
            execution_id=execution_id,
            payload_hash=payload_hash,
            ed25519_signature=b"\x00" * 64,
            ed25519_key_id="ed",
            ml_dsa_signature=b"\x00" * 3309,
            ml_dsa_key_id="ml",
            algorithm="ed25519+ml-dsa-65",
        )
    )
    await session.flush()
    return receipt_id


@pytest.mark.asyncio
async def test_append_assigns_monotonic_index(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    pid = UUID(fx["project_id"])
    aid = UUID(fx["agent_id"])
    appender = MerkleAppender()

    indices: list[int] = []
    async with session_scope() as session:
        for _ in range(5):
            payload_hash = secrets.token_bytes(32)
            receipt_id = await _seed_receipt(session, pid, aid, payload_hash)
            idx, root, size, _ = await appender.append(
                session, project_id=pid, receipt_id=receipt_id, payload_hash=payload_hash
            )
            await appender.persist_leaf(
                session,
                project_id=pid,
                leaf_index=idx,
                leaf_hash=payload_hash,
                receipt_id=receipt_id,
            )
            # Also update the receipt row so the FK chain matches
            from sqlalchemy import update

            await session.execute(
                update(Receipt)
                .where(Receipt.id == receipt_id)
                .values(merkle_root=root, merkle_tree_size=size),
            )
            indices.append(idx)
    assert indices == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_append_generates_valid_inclusion_proof(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    pid = UUID(fx["project_id"])
    aid = UUID(fx["agent_id"])
    appender = MerkleAppender()
    async with session_scope() as session:
        payload_hash = secrets.token_bytes(32)
        receipt_id = await _seed_receipt(session, pid, aid, payload_hash)
        idx, root, size, path = await appender.append(
            session, project_id=pid, receipt_id=receipt_id, payload_hash=payload_hash
        )
        await appender.persist_leaf(
            session,
            project_id=pid,
            leaf_index=idx,
            leaf_hash=payload_hash,
            receipt_id=receipt_id,
        )
        proof = InclusionProof(leaf_index=idx, tree_size=size, path=path)
        assert verify_inclusion(root, payload_hash, proof) is True


@pytest.mark.asyncio
async def test_append_isolated_across_projects(client: AsyncClient) -> None:
    fx_a = await bootstrap_project_with_api_key(client)
    fx_b = await bootstrap_project_with_api_key(client)
    appender = MerkleAppender()
    pid_a = UUID(fx_a["project_id"])
    pid_b = UUID(fx_b["project_id"])
    aid_a = UUID(fx_a["agent_id"])
    aid_b = UUID(fx_b["agent_id"])

    async with session_scope() as session:
        for pid, aid in ((pid_a, aid_a), (pid_b, aid_b), (pid_a, aid_a)):
            ph = secrets.token_bytes(32)
            rid = await _seed_receipt(session, pid, aid, ph)
            idx, root, size, _ = await appender.append(
                session, project_id=pid, receipt_id=rid, payload_hash=ph
            )
            await appender.persist_leaf(
                session, project_id=pid, leaf_index=idx, leaf_hash=ph, receipt_id=rid
            )
            from sqlalchemy import update

            await session.execute(
                update(Receipt)
                .where(Receipt.id == rid)
                .values(merkle_root=root, merkle_tree_size=size)
            )

    async with session_scope() as session:
        leaves_a = await appender.rebuild_tree(session, project_id=pid_a)
        leaves_b = await appender.rebuild_tree(session, project_id=pid_b)
    assert len(leaves_a) == 2
    assert len(leaves_b) == 1


@pytest.mark.asyncio
async def test_concurrent_appends_to_same_project_serialize(client: AsyncClient) -> None:
    """Advisory lock must serialize: N concurrent appends get N distinct indices."""

    fx = await bootstrap_project_with_api_key(client)
    pid = UUID(fx["project_id"])
    aid = UUID(fx["agent_id"])
    appender = MerkleAppender()

    n_concurrent = 6

    async def one_append() -> int:
        async with session_scope() as session:
            ph = secrets.token_bytes(32)
            rid = await _seed_receipt(session, pid, aid, ph)
            idx, root, size, _ = await appender.append(
                session, project_id=pid, receipt_id=rid, payload_hash=ph
            )
            await appender.persist_leaf(
                session,
                project_id=pid,
                leaf_index=idx,
                leaf_hash=ph,
                receipt_id=rid,
            )
            from sqlalchemy import update

            await session.execute(
                update(Receipt)
                .where(Receipt.id == rid)
                .values(merkle_root=root, merkle_tree_size=size)
            )
            return idx

    results = await asyncio.gather(*(one_append() for _ in range(n_concurrent)))
    assert sorted(results) == list(range(n_concurrent))
