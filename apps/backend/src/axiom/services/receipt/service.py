"""High-level orchestrator: routers call this; it runs the full pipeline.

Keeps the router's body trivial — one call in, one ``PipelineContext`` out.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from axiom.services.explanation.engine import ExplanationEngine
from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from axiom.services.pipeline.runner import PipelineRunner
from axiom.services.pipeline.stages.authority import AuthorityStage
from axiom.services.pipeline.stages.dispatch import DispatchStage
from axiom.services.pipeline.stages.evidence import EvidenceStage
from axiom.services.pipeline.stages.intent import IntentStage
from axiom.services.pipeline.stages.receipt import ReceiptStage
from axiom.services.pipeline.stages.strategy import StrategyStage
from axiom.services.prompt_injection.detector import InjectionDetector
from axiom.services.receipt.keys import SigningKeys, get_signing_keys
from axiom.services.receipt.merkle_append import MerkleAppender


def build_runner(
    session: AsyncSession,
    *,
    keys: SigningKeys | None = None,
    injection_detector: InjectionDetector | None = None,
    explanation_engine: ExplanationEngine | None = None,
    merkle_appender: MerkleAppender | None = None,
) -> PipelineRunner:
    """Compose the six concrete stages into a ``PipelineRunner``.

    Every call constructs a fresh runner because Strategy + Authority + Receipt
    stages hold the AsyncSession, which is request-scoped.
    """

    keys = keys or get_signing_keys()
    runner = PipelineRunner(
        stages=(
            IntentStage(detector=injection_detector),
            StrategyStage(session),
            AuthorityStage(session, explanation_engine=explanation_engine),
            DispatchStage(),
            EvidenceStage(
                evidence_key=keys.evidence_key,
                evidence_key_id=keys.evidence_key_id,
            ),
            ReceiptStage(
                session,
                ed25519_private=keys.ed25519_private,
                ed25519_public=keys.ed25519_public,
                ml_dsa_private=keys.ml_dsa_private,
                ml_dsa_public=keys.ml_dsa_public,
                merkle_appender=merkle_appender,
            ),
        ),
    )
    return runner


class ReceiptService:
    """Thin orchestration surface for the govern router."""

    def __init__(self, session: AsyncSession, *, keys: SigningKeys | None = None) -> None:
        self._session = session
        self._keys = keys or get_signing_keys()

    async def process(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        api_key_id: UUID,
        correlation_id: str,
        action: dict[str, Any],
        mode: PipelineMode,
    ) -> PipelineContext:
        runner = build_runner(self._session, keys=self._keys)
        ctx = PipelineContext(
            project_id=project_id,
            agent_id=agent_id,
            api_key_id=api_key_id,
            correlation_id=correlation_id,
            action=action,
            mode=mode,
            requested_at=datetime.now(UTC),
        )
        return await runner.run(ctx)
