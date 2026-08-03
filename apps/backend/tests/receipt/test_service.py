"""ReceiptService end-to-end: runs the full 6-stage pipeline and persists all 3 rows."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from axiom.db import session_scope
from axiom.models.execution import Execution
from axiom.models.merkle_node import MerkleNode
from axiom.models.receipt import Receipt
from axiom.services.pipeline.protocols import PipelineMode
from axiom.services.receipt.service import ReceiptService
from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.mark.asyncio
async def test_receipt_service_persists_all_three_rows(client: AsyncClient) -> None:
    rules = [
        {
            "id": "allow_chat",
            "description": "Chat is allowed",
            "when": {"type": "chat"},
            "then": "approve",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async with session_scope() as session:
        svc = ReceiptService(session)
        ctx = await svc.process(
            project_id=UUID(fx["project_id"]),
            agent_id=UUID(fx["agent_id"]),
            api_key_id=UUID(fx["api_key_id"]),
            correlation_id="corr-1",
            action={"type": "chat", "body": "hello"},
            mode=PipelineMode.ENFORCE,
        )
        assert ctx.receipt_id is not None
        assert ctx.execution_id is not None
        assert ctx.merkle_leaf_index == 0
        assert ctx.decision is not None
        assert ctx.decision.verdict.value == "approve"
        assert ctx.dispatched is True

    async with session_scope() as session:
        assert (await session.scalar(select(func.count()).select_from(Execution)) or 0) >= 1
        assert (await session.scalar(select(func.count()).select_from(Receipt)) or 0) >= 1
        assert (await session.scalar(select(func.count()).select_from(MerkleNode)) or 0) >= 1


@pytest.mark.asyncio
async def test_receipt_service_denies_when_no_policy(client: AsyncClient) -> None:
    """Bootstrap a project with no policy rule — the seeded policy has []
    rules, so the policy IS found but returns default DENY."""

    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        svc = ReceiptService(session)
        ctx = await svc.process(
            project_id=UUID(fx["project_id"]),
            agent_id=UUID(fx["agent_id"]),
            api_key_id=UUID(fx["api_key_id"]),
            correlation_id="corr-n",
            action={"type": "anything"},
            mode=PipelineMode.ENFORCE,
        )
        assert ctx.decision is not None
        assert ctx.decision.verdict.value == "deny"
        assert ctx.receipt_id is not None


@pytest.mark.asyncio
async def test_receipt_service_shadow_never_dispatches(client: AsyncClient) -> None:
    rules = [
        {
            "id": "allow_all",
            "description": "Allow",
            "when": {"type": "x"},
            "then": "approve",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    async with session_scope() as session:
        svc = ReceiptService(session)
        ctx = await svc.process(
            project_id=UUID(fx["project_id"]),
            agent_id=UUID(fx["agent_id"]),
            api_key_id=UUID(fx["api_key_id"]),
            correlation_id="corr-s",
            action={"type": "x"},
            mode=PipelineMode.SHADOW,
        )
        assert ctx.dispatched is False
        assert ctx.decision is not None
        assert ctx.decision.verdict.value == "approve"
