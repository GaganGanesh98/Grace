"""Fire-and-forget escalation dispatch (mirrors events.schedule_* pattern).

Triggered when an action is held/escalated (approval created). Loads the
governance receipt/intent/verdict, builds the structured payload, signs it, and
POSTs it to the n8n webhook. Never raises into the request path — governance
must not break because n8n is down.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from uuid import UUID

import structlog

from axiom.config import Settings, get_settings
from axiom.db import session_scope
from axiom.models.governance import (
    GovernanceIntent,
    GovernanceReceipt,
    GovernanceVerdict,
)
from axiom.schemas.escalation import EscalationAction, EscalationPayload, EscalationPolicy
from axiom.services.escalation.signing import SIGNATURE_HEADER, sign_body
from axiom.services.escalation.webhook_client import post_with_retry

logger = structlog.get_logger(__name__)


def build_payload(
    settings: Settings,
    receipt: GovernanceReceipt,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
) -> EscalationPayload:
    rule_ids = [
        str(rule["id"])
        for rule in (verdict.rules_evaluated or [])
        if isinstance(rule, dict) and rule.get("id")
    ]
    return EscalationPayload(
        receipt_id=receipt.id,
        project_id=receipt.project_id,
        agent_id=str(intent.agent_id),
        action=EscalationAction(
            type=intent.action_type,
            target=intent.target,
            parameters=dict(intent.parameters or {}),
        ),
        policy_violated=EscalationPolicy(
            policy_version=verdict.policy_version,
            rule_ids=rule_ids,
            reason=verdict.reason,
        ),
        verdict=verdict.verdict,
        severity=intent.risk_declared or verdict.risk_assessed,
        timestamp=receipt.created_at,
        expires_at=receipt.approval_expires_at,
        link=f"{settings.app_url.rstrip('/')}/receipts/{receipt.id}",
        callback_url=f"{settings.api_url.rstrip('/')}/webhooks/n8n/escalation-result",
    )


async def dispatch_escalation(project_id: UUID, receipt_id: UUID) -> None:
    settings = get_settings()
    if not settings.escalation_enabled or not settings.n8n_escalation_webhook_url:
        return

    async with session_scope() as db:
        receipt = await db.get(GovernanceReceipt, receipt_id)
        if receipt is None or receipt.project_id != project_id:
            return
        intent = await db.get(GovernanceIntent, receipt.intent_id)
        verdict = await db.get(GovernanceVerdict, receipt.verdict_id)
        if intent is None or verdict is None:
            return
        payload = build_payload(settings, receipt, intent, verdict)

    body = payload.model_dump_json().encode("utf-8")
    headers = {"Content-Type": "application/json"}
    secret = settings.n8n_callback_secret
    if secret is not None:
        headers[SIGNATURE_HEADER] = sign_body(secret.get_secret_value(), body)

    try:
        response = await post_with_retry(
            settings.n8n_escalation_webhook_url, content=body, headers=headers
        )
        logger.info(
            "escalation.dispatched", receipt_id=str(receipt_id), status=response.status_code
        )
    except Exception as exc:  # noqa: BLE001 — escalation must never break governance
        logger.warning("escalation.dispatch_failed", receipt_id=str(receipt_id), error=str(exc))


def schedule_escalation(project_id: UUID, receipt_id: UUID) -> None:
    """Schedule dispatch on the running loop, post-commit. Safe from handlers."""
    if not get_settings().escalation_enabled:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("escalation.no_event_loop", receipt_id=str(receipt_id))
        return
    task = loop.create_task(dispatch_escalation(project_id, receipt_id))

    def _done(finished: asyncio.Task[None]) -> None:
        with suppress(Exception):  # any error was already logged inside dispatch
            finished.result()

    task.add_done_callback(_done)
