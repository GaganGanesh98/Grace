"""Edge paths for /v1/verify: orphan receipt, unsigned receipt, wrong key_id."""

from __future__ import annotations

import secrets

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from axiom.db import session_scope
from axiom.models.execution import Execution
from axiom.models.receipt import Receipt
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


async def _mint(client: AsyncClient) -> tuple[str, str]:
    rules = [{"id": "x", "description": "ok", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    return r.json()["receipt_id"], fx["project_id"]


@pytest.mark.asyncio
async def test_verify_unsigned_receipt_404(client: AsyncClient) -> None:
    """A receipt with NULL merkle_root (pre-Phase-2 row shape) returns 404."""

    receipt_id, _ = await _mint(client)
    async with session_scope() as session:
        await session.execute(
            update(Receipt)
            .where(Receipt.id == receipt_id)
            .values(merkle_root=None, merkle_tree_size=None)
        )
    r = await client.get(f"/v1/verify/{receipt_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_verify_orphan_receipt_branch_covered(client: AsyncClient) -> None:
    """Directly exercise the orphan-receipt branch by mocking db.scalar to return None.

    The database FK prevents a true orphan, so we simulate the defensive branch
    via a patched session.
    """

    from unittest.mock import patch

    receipt_id, _ = await _mint(client)

    orig_scalar = None

    async def _patched_scalar(*args, **kwargs):
        # Return None only for the Execution lookup (the one that selects Execution).
        stmt = args[0] if args else kwargs.get("statement")
        sql = str(stmt).lower() if stmt is not None else ""
        if "executions" in sql and "select" in sql:
            return None
        return await orig_scalar(*args, **kwargs)

    # Patch AsyncSession.scalar on the whole class for this call only.
    from sqlalchemy.ext.asyncio import AsyncSession

    orig_scalar = AsyncSession.scalar

    async def _scalar_stub(self, statement, *args, **kwargs):
        text_sql = str(statement).lower()
        if "from executions" in text_sql:
            return None
        return await orig_scalar(self, statement, *args, **kwargs)

    with patch.object(AsyncSession, "scalar", _scalar_stub):
        r = await client.get(f"/v1/verify/{receipt_id}")
    assert r.status_code == 404
    _ = update, secrets, session_scope, Execution, Receipt  # keep imports used


@pytest.mark.asyncio
async def test_verify_wrong_key_id_marks_signatures_invalid(client: AsyncClient) -> None:
    """If the stored ed25519_key_id no longer matches the loaded key, verify marks it invalid."""

    receipt_id, _ = await _mint(client)
    async with session_scope() as session:
        await session.execute(
            update(Receipt).where(Receipt.id == receipt_id).values(ed25519_key_id="bogus-id")
        )
    r = await client.get(f"/v1/verify/{receipt_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["verified"] is False
    assert body["verification_details"]["ed25519_signature_valid"] is False


@pytest.mark.asyncio
async def test_verify_wrong_mldsa_key_id_marks_signatures_invalid(client: AsyncClient) -> None:
    receipt_id, _ = await _mint(client)
    async with session_scope() as session:
        await session.execute(
            update(Receipt).where(Receipt.id == receipt_id).values(ml_dsa_key_id="bogus-id")
        )
    r = await client.get(f"/v1/verify/{receipt_id}")
    body = r.json()
    assert body["verified"] is False
    assert body["verification_details"]["ml_dsa_signature_valid"] is False
