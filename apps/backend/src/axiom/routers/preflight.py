"""POST /v1/preflight — predict verdict without commitment."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import get_preflight_service, require_api_key
from axiom.middleware.rate_limit import api_key_limit_key, limiter
from axiom.schemas.preflight import PreflightRequest, PreflightResponse, RelatedPolicy
from axiom.services import policies as policies_service
from axiom.services.api_key import APIKeyContext
from axiom.services.crypto.canonical_json import NonCanonicalizableError, canonicalize
from axiom.services.preflight.service import PreflightService

_MAX_BODY_BYTES = 100 * 1024

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "/preflight",
    response_model=PreflightResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("600/minute", key_func=api_key_limit_key)
async def preflight(
    request: Request,
    body: PreflightRequest,
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[PreflightService, Depends(get_preflight_service)],
) -> PreflightResponse:
    """Predict governance verdict without committing.

    Same authentication, project scoping, and rate limit style as /v1/govern
    (but 600/min vs 100/min — pre-flight is cheap).

    Request body: {"action": {...}, "agent_id": "uuid", "mode": "enforce" | "shadow"}
    Action body cap: 100KB (same as /v1/govern).

    Response: PreflightResponse — see schema.

    IMPORTANT: Pre-flight does NOT emit a receipt. To commit the action, call /v1/govern.
    """
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request body exceeds 100 KB cap for /v1/preflight",
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header",
            ) from exc

    try:
        canonicalize(body.action)
    except (NonCanonicalizableError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action payload: {exc}",
        ) from exc

    prediction = await service.predict(
        session=db,
        project_id=api_ctx.project_id,
        agent_id=body.agent_id,
        api_key_id=api_ctx.api_key_id,
        action=body.action,
        mode=body.mode,
    )

    logger.info(
        "preflight.completed",
        correlation_id=prediction.correlation_id,
        prediction_id=prediction.prediction_id,
        project_id=str(api_ctx.project_id),
        cached=prediction.cached,
    )

    # Advisory semantic context — opt-in, additive, and fail-soft: it never
    # affects the predicted verdict and never fails the request.
    related_policies: list[RelatedPolicy] = []
    if body.include_related_policies:
        query_text = policies_service.action_query_text(body.action)
        if query_text:
            try:
                matches = await policies_service.search_policies(
                    db, project_id=api_ctx.project_id, query_text=query_text, k=5
                )
                related_policies = [
                    RelatedPolicy(
                        policy_id=policy.id,
                        slug=policy.slug,
                        name=policy.name,
                        version=policy.version,
                        similarity=score,
                    )
                    for policy, score in matches
                ]
            except Exception:  # noqa: BLE001 — advisory context must never fail preflight
                logger.warning("preflight.related_policies_failed", exc_info=True)

    return PreflightResponse(
        prediction_id=prediction.prediction_id,
        predicted_verdict=prediction.predicted_verdict,
        rule_id=prediction.rule_id,
        policy_id=prediction.policy_id,
        policy_version=prediction.policy_version,
        reasoning=prediction.reasoning,
        explanation=prediction.explanation,
        probably_definitive=prediction.probably_definitive,
        confidence=prediction.confidence,
        cached=prediction.cached,
        cache_age_seconds=prediction.cache_age_seconds,
        correlation_id=prediction.correlation_id,
        related_policies=related_policies,
    )
