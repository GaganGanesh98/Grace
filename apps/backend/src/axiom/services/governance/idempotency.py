"""Run-scoped idempotency for external orchestrators (Phase 9.1).

An orchestrator retries. n8n retries on timeout, on a 5xx, and when a human
clicks "retry execution". Without a claim, each of those mints a second receipt
for one real-world action, and the audit chain then says the action was governed
twice — which is worse than not recording it at all.

The claim is Redis, not Postgres, on purpose: it is cache-shaped state with a
TTL, it must be checkable before the transaction that would create the receipt,
and losing it degrades to "a retry creates a duplicate receipt" rather than to
data loss. Same reasoning as the rate limiter using Redis rather than a table.

This is not workflow state. Grace stores the run id long enough to recognise a
replay and nothing else — no status, no step position, no resumption. n8n owns
orchestration (AP-1.8 in docs/ANTIPATTERN_LIBRARY.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import structlog

from axiom.services.redis_client import get_redis

logger = structlog.get_logger(__name__)

#: Marks a claim whose governed action has not finished yet. A concurrent
#: duplicate sees this and is told to retry rather than racing to a second receipt.
IN_FLIGHT = "__in_flight__"

_KEY_PREFIX = "axiom:n8n:action"


class ClaimState(StrEnum):
    CLAIMED = "claimed"  # we won; go govern the action
    IN_FLIGHT = "in_flight"  # someone else is mid-flight; caller should retry
    REPLAY = "replay"  # already governed; caller returns the recorded receipt


@dataclass(frozen=True)
class Claim:
    state: ClaimState
    receipt_id: str | None = None


def run_key(workflow_id: str, workflow_run_id: str) -> str:
    return f"{_KEY_PREFIX}:{workflow_id}:{workflow_run_id}"


async def claim_run(workflow_id: str, workflow_run_id: str, *, ttl_seconds: int) -> Claim:
    """Try to claim this workflow run.

    Returns ``CLAIMED`` when this caller should govern the action, ``REPLAY``
    with the previously recorded receipt id when it already has been, and
    ``IN_FLIGHT`` when a concurrent request is still working on it.
    """
    key = run_key(workflow_id, workflow_run_id)
    redis = get_redis()
    won = await redis.set(key, IN_FLIGHT, nx=True, ex=ttl_seconds)
    if won:
        return Claim(state=ClaimState.CLAIMED)

    existing = await redis.get(key)
    if existing is None or existing == IN_FLIGHT:
        # Either a concurrent request is mid-flight, or the claim expired between
        # the SET and the GET. Both mean "do not govern this now".
        return Claim(state=ClaimState.IN_FLIGHT)
    return Claim(state=ClaimState.REPLAY, receipt_id=str(existing))


async def record_receipt(
    workflow_id: str, workflow_run_id: str, receipt_id: str, *, ttl_seconds: int
) -> None:
    """Attach the receipt to a claim this caller won, so replays can find it."""
    await get_redis().set(run_key(workflow_id, workflow_run_id), receipt_id, ex=ttl_seconds)


async def release_claim(workflow_id: str, workflow_run_id: str) -> None:
    """Drop a claim whose governed action failed, so a retry can succeed.

    Leaving a failed run claimed would strand the workflow for the whole TTL.
    """
    try:
        await get_redis().delete(run_key(workflow_id, workflow_run_id))
    except Exception as exc:  # noqa: BLE001 — cleanup must not mask the real error
        logger.warning(
            "n8n.action.claim_release_failed",
            workflow_run_id=workflow_run_id,
            error=str(exc),
        )
