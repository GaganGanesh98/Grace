"""POST /v1/disclose — selective disclosure with per-receipt Merkle proofs.

WEDGE. API-key auth required. 30 req/min per key.

Returns matching receipts plus a fresh Merkle inclusion proof for each.
Scope is IMPLICIT from the authenticated API key's project_id — callers
cannot disclose across projects. Evidence ciphertext is decrypted with
the AXIOM-wide evidence key (authorized by the valid API key) and
returned as plaintext; the caller is responsible for down-stream handling
(GDPR, subpoena, internal review).
"""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.deps import require_api_key
from axiom.middleware.rate_limit import api_key_limit_key, limiter
from axiom.models.execution import Execution
from axiom.models.receipt import Receipt
from axiom.schemas.governance import (
    DisclosedReceipt,
    DiscloseRequest,
    DiscloseResponse,
    InclusionProofSchema,
)
from axiom.services.api_key import APIKeyContext
from axiom.services.crypto import aes_gcm
from axiom.services.crypto.aes_gcm import AESGCMCiphertext
from axiom.services.crypto.merkle import build_tree, inclusion_proof
from axiom.services.policy.evaluator import Verdict
from axiom.services.receipt.keys import get_signing_keys
from axiom.services.receipt.merkle_append import MerkleAppender

router = APIRouter()
logger = structlog.get_logger(__name__)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


@router.post("/disclose", response_model=DiscloseResponse)
@limiter.limit("30/minute", key_func=api_key_limit_key)
async def disclose(
    request: Request,
    body: DiscloseRequest,
    api_ctx: Annotated[APIKeyContext, Depends(require_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DiscloseResponse:
    _ = request  # slowapi needs the parameter
    if body.from_date > body.to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be <= to_date",
        )

    conditions = [
        Execution.project_id == api_ctx.project_id,
        Execution.created_at >= body.from_date,
        Execution.created_at <= body.to_date,
    ]
    if body.agent_id is not None:
        conditions.append(Execution.agent_id == body.agent_id)
    if body.action_type is not None:
        conditions.append(Execution.action["type"].astext == body.action_type)

    total = int(
        await db.scalar(select(func.count()).select_from(Execution).where(*conditions)) or 0
    )

    rows = await db.execute(
        select(Receipt, Execution)
        .join(Execution, Execution.id == Receipt.execution_id)
        .where(*conditions)
        .order_by(Execution.created_at.desc())
        .offset((body.page - 1) * body.per_page)
        .limit(body.per_page),
    )
    pairs = rows.all()

    keys = get_signing_keys()
    appender = MerkleAppender()
    disclosed: list[DisclosedReceipt] = []

    for receipt, execution in pairs:
        if execution.project_id != api_ctx.project_id:
            logger.error(
                "disclose.cross_project_leak_blocked",
                api_key_id=str(api_ctx.api_key_id),
                execution_project=str(execution.project_id),
                api_key_project=str(api_ctx.project_id),
            )
            continue
        if receipt.merkle_root is None or receipt.merkle_tree_size is None:
            continue

        historical = await appender.rebuild_tree(
            db,
            project_id=execution.project_id,
            up_to_size=receipt.merkle_tree_size,
        )
        leaf_index: int | None = None
        for i, h in enumerate(historical):
            if h == receipt.payload_hash:
                leaf_index = i
                break
        if leaf_index is None:
            continue
        tree = build_tree(historical)
        proof = inclusion_proof(tree, leaf_index)

        evidence: dict[str, Any] = {"decrypted": False}
        if (
            receipt.evidence_nonce is not None
            and receipt.evidence_ciphertext is not None
            and receipt.evidence_key_id is not None
            and receipt.evidence_key_id == keys.evidence_key_id
        ):
            try:
                plaintext = aes_gcm.decrypt(
                    keys.evidence_key,
                    AESGCMCiphertext(
                        nonce=receipt.evidence_nonce,
                        ciphertext=receipt.evidence_ciphertext,
                        key_id=receipt.evidence_key_id,
                    ),
                )
                evidence = {"decrypted": True, "body": json.loads(plaintext.decode("utf-8"))}
            except Exception as exc:  # noqa: BLE001 - bad data shouldn't break disclosure
                logger.warning(
                    "disclose.evidence_decrypt_failed",
                    receipt_id=receipt.id,
                    error=type(exc).__name__,
                )
                evidence = {"decrypted": False, "error": "decryption_failed"}

        disclosed.append(
            DisclosedReceipt(
                receipt_id=receipt.id,
                execution_id=execution.id,
                created_at=execution.created_at,
                verdict=Verdict(execution.verdict),
                policy_id=execution.policy_id,
                policy_version=execution.policy_version,
                reasoning=execution.reasoning,
                explanation=(evidence.get("body") or {}).get("explanation")
                if evidence.get("decrypted")
                else None,
                correlation_id=execution.correlation_id,
                inclusion_proof=InclusionProofSchema(
                    leaf_index=leaf_index,
                    tree_size=receipt.merkle_tree_size,
                    path=[_b64(p) for p in proof.path],
                ),
                merkle_root=_b64(receipt.merkle_root),
                merkle_tree_size=receipt.merkle_tree_size,
                evidence=evidence,
            )
        )

    logger.info(
        "disclose.served",
        api_key_id=str(api_ctx.api_key_id),
        project_id=str(api_ctx.project_id),
        total=total,
        page=body.page,
        returned=len(disclosed),
    )

    return DiscloseResponse(
        total=total,
        page=body.page,
        per_page=body.per_page,
        receipts=disclosed,
    )
