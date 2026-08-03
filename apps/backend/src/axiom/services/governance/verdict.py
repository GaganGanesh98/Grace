"""Stage 4: verdict persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.governance import GovernanceIntent, GovernanceVerdict
from axiom.services.governance.policy import PolicyResult


async def render_verdict(
    db: AsyncSession,
    intent: GovernanceIntent,
    policy_result: PolicyResult,
    context: dict,
) -> GovernanceVerdict:
    verdict = GovernanceVerdict(
        intent_id=intent.id,
        verdict=policy_result.verdict,
        reason=policy_result.reason,
        policy_version=policy_result.policy_version,
        rules_evaluated=list(policy_result.rules_evaluated),
        risk_assessed=policy_result.risk_assessed,
        context=dict(context),
    )
    db.add(verdict)
    await db.flush()
    return verdict
