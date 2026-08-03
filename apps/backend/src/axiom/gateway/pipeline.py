"""Governance pipeline for gateway requests (direct service calls)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from axiom.gateway.classifier import GatewayClassification
from axiom.models.governance import (
    GovernanceChain,
    GovernanceIntent,
    GovernanceReceipt,
    GovernanceVerdict,
)
from axiom.schemas.governance import GovernRequest
from axiom.services.escalation import schedule_escalation
from axiom.services.events import (
    schedule_approval_created,
    schedule_receipt_sealed,
)
from axiom.services.governance.chain import (
    ChainValidationError,
    auto_close_stale_chains,
    get_or_create_chain,
    update_chain_stats,
)
from axiom.services.governance.context import enrich_context
from axiom.services.governance.intent import declare_intent
from axiom.services.governance.policy import evaluate_policy
from axiom.services.governance.receipt import create_pending_receipt, seal_receipt
from axiom.services.governance.verdict import render_verdict
from axiom.services.governance.verification import VerificationResult, verify_execution


@dataclass(frozen=True)
class DenyOutcome:
    receipt_id: UUID


@dataclass(frozen=True)
class HoldOutcome:
    receipt_id: UUID
    approval_expires_at: datetime | None


@dataclass(frozen=True)
class AllowOutcome:
    receipt_id: UUID
    intent_id: UUID
    verdict_id: UUID
    chain_id: UUID | None


GatewayOutcomeKind = Literal["deny", "hold", "allow"]


@dataclass(frozen=True)
class GatewayGovernanceResult:
    kind: GatewayOutcomeKind
    deny: DenyOutcome | None = None
    hold: HoldOutcome | None = None
    allow: AllowOutcome | None = None


async def run_gateway_governance(
    db: AsyncSession,
    *,
    project_id: UUID,
    classification: GatewayClassification,
    agent_id: str,
) -> GatewayGovernanceResult:
    """Evaluate policy and persist intent/receipt; seal immediately on deny."""
    await auto_close_stale_chains(db, project_id)
    try:
        chain = await get_or_create_chain(
            db,
            project_id,
            agent_id,
            "gateway",
            None,
        )
    except ChainValidationError:
        chain = None

    body = GovernRequest(
        agent_id=agent_id,
        action_type=classification.action_type,
        target=classification.target,
        parameters={"provider": classification.provider},
        risk=classification.risk,
        mode="enforce",
        metadata={"source": "gateway"},
        workflow="gateway",
        chain_id=None,
    )
    intent = await declare_intent(db, project_id, body, chain_id=chain.id if chain else None)
    context = await enrich_context(db, intent)
    policy_result = evaluate_policy(intent, context)
    verdict = await render_verdict(db, intent, policy_result, context)
    receipt = await create_pending_receipt(db, intent=intent, verdict=verdict)

    if verdict.verdict == "hold" and intent.mode != "shadow":
        receipt.approval_status = "pending"
        receipt.approval_expires_at = datetime.now(UTC) + timedelta(minutes=30)

    if chain is not None:
        await update_chain_stats(db, chain, verdict.verdict, None)

    if verdict.verdict == "deny":
        blocked = {
            "target": intent.target,
            "action_type": intent.action_type,
            "risk": intent.risk_declared,
            "blocked": True,
        }
        vres = verify_execution(intent, blocked)
        await seal_receipt(
            db,
            receipt=receipt,
            intent=intent,
            verdict=verdict,
            execution_data=blocked,
            executed_at=datetime.now(UTC),
            verification_result=vres,
        )
        if chain is not None and receipt.verification is not None:
            ch2 = await db.get(GovernanceChain, chain.id)
            if ch2 is not None:
                await update_chain_stats(db, ch2, None, receipt.verification)
        await db.commit()
        schedule_receipt_sealed(
            project_id,
            receipt_id=receipt.id,
            verdict_raw=verdict.verdict,
            agent_id=str(intent.agent_id),
        )
        return GatewayGovernanceResult(kind="deny", deny=DenyOutcome(receipt_id=receipt.id))

    if verdict.verdict == "hold":
        await db.commit()
        if intent.mode != "shadow" and receipt.approval_expires_at is not None:
            schedule_approval_created(
                project_id,
                receipt_id=receipt.id,
                expires_at=receipt.approval_expires_at,
            )
            # Additive: notify the n8n escalation flow (no-op unless ESCALATION_ENABLED).
            schedule_escalation(project_id, receipt.id)
        appr_expires = receipt.approval_expires_at if intent.mode != "shadow" else None
        return GatewayGovernanceResult(
            kind="hold",
            hold=HoldOutcome(receipt_id=receipt.id, approval_expires_at=appr_expires),
        )

    await db.commit()
    return GatewayGovernanceResult(
        kind="allow",
        allow=AllowOutcome(
            receipt_id=receipt.id,
            intent_id=intent.id,
            verdict_id=verdict.id,
            chain_id=intent.chain_id,
        ),
    )


async def seal_after_success(
    db: AsyncSession,
    *,
    receipt_id: UUID,
    project_id: UUID,
    execution_data: dict,
    executed_at: datetime,
) -> None:
    """Load pending receipt and seal after successful provider call."""
    receipt = await db.get(GovernanceReceipt, receipt_id)
    if receipt is None or receipt.project_id != project_id:
        return
    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        return
    vres = verify_execution(intent, execution_data)
    await seal_receipt(
        db,
        receipt=receipt,
        intent=intent,
        verdict=verdict,
        execution_data=execution_data,
        executed_at=executed_at,
        verification_result=vres,
    )
    if intent.chain_id is not None:
        ch = await db.get(GovernanceChain, intent.chain_id)
        if ch is not None and receipt.verification is not None:
            await update_chain_stats(db, ch, None, receipt.verification)
    await db.commit()
    schedule_receipt_sealed(
        project_id,
        receipt_id=receipt.id,
        verdict_raw=verdict.verdict,
        agent_id=str(intent.agent_id),
    )


async def seal_after_transport_failure(
    db: AsyncSession,
    *,
    receipt_id: UUID,
    project_id: UUID,
    error_message: str,
) -> None:
    """Seal with verification failure when the outbound call could not complete."""
    receipt = await db.get(GovernanceReceipt, receipt_id)
    if receipt is None or receipt.project_id != project_id:
        return
    intent = await db.get(GovernanceIntent, receipt.intent_id)
    verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
    if intent is None or verdict is None:
        return
    execution_data = {
        "target": intent.target,
        "action_type": intent.action_type,
        "risk": intent.risk_declared,
        "error": error_message,
    }
    vres = VerificationResult(passed=False, mismatches=[{"field": "gateway", "detail": error_message}], status="fail")
    await seal_receipt(
        db,
        receipt=receipt,
        intent=intent,
        verdict=verdict,
        execution_data=execution_data,
        executed_at=datetime.now(UTC),
        verification_result=vres,
    )
    if intent.chain_id is not None:
        ch = await db.get(GovernanceChain, intent.chain_id)
        if ch is not None and receipt.verification is not None:
            await update_chain_stats(db, ch, None, receipt.verification)
    await db.commit()
    schedule_receipt_sealed(
        project_id,
        receipt_id=receipt.id,
        verdict_raw=verdict.verdict,
        agent_id=str(intent.agent_id),
    )
