"""GET /v1/verify/{receipt_id} — public receipt verification.

WEDGE. No auth. 60 req/min per IP. Returns only public metadata; never
leaks evidence ciphertext or nonce. Anyone with a receipt_id can ask:
  * Are both signatures (Ed25519 + ML-DSA-65) valid?
  * Does the inclusion proof check against the stored Merkle root?
  * Does the stored payload_hash match what the signer signed?

All four checks must pass for ``verified = true``.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.db import get_db
from axiom.middleware.rate_limit import limiter
from axiom.models.execution import Execution
from axiom.models.receipt import Receipt
from axiom.schemas.governance import (
    InclusionProofSchema,
    VerificationDetails,
    VerifyResponse,
)
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.crypto.merkle import InclusionProof, verify_inclusion
from axiom.services.policy.evaluator import Verdict
from axiom.services.receipt.keys import get_signing_keys
from axiom.services.receipt.merkle_append import MerkleAppender

router = APIRouter()
logger = structlog.get_logger(__name__)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


@router.get("/verify/{receipt_id}", response_model=VerifyResponse)
@limiter.limit("60/minute")
async def verify(
    request: Request,
    receipt_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyResponse:
    _ = request  # slowapi needs the parameter
    receipt = await db.get(Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )
    execution = await db.scalar(select(Execution).where(Execution.id == receipt.execution_id))
    if execution is None:
        logger.warning("verify.orphan_receipt", receipt_id=receipt_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )

    merkle_root = receipt.merkle_root
    merkle_tree_size = receipt.merkle_tree_size
    if merkle_root is None or merkle_tree_size is None:
        logger.warning("verify.unsigned_receipt", receipt_id=receipt_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )

    appender = MerkleAppender()
    historical_leaves = await appender.rebuild_tree(
        db,
        project_id=execution.project_id,
        up_to_size=merkle_tree_size,
    )
    leaf_index: int | None = None
    for i, payload_hash in enumerate(historical_leaves):
        if payload_hash == receipt.payload_hash:
            leaf_index = i
            break

    if leaf_index is None or len(historical_leaves) != merkle_tree_size:
        logger.warning("verify.merkle_state_mismatch", receipt_id=receipt_id)
        merkle_valid = False
        audit_path: tuple[bytes, ...] = ()
    else:
        from axiom.services.crypto.merkle import build_tree, inclusion_proof

        tree = build_tree(historical_leaves)
        proof = inclusion_proof(tree, leaf_index)
        audit_path = proof.path
        merkle_valid = verify_inclusion(
            merkle_root,
            receipt.payload_hash,
            InclusionProof(
                leaf_index=leaf_index,
                tree_size=merkle_tree_size,
                path=audit_path,
            ),
        )

    keys = get_signing_keys()
    signed_body = {
        "algorithm": receipt.algorithm,
        "receipt_id": receipt.id,
        "payload_hash": _b64(receipt.payload_hash),
        "evidence_key_id": receipt.evidence_key_id or "",
        "merkle": {
            "leaf_index": leaf_index if leaf_index is not None else -1,
            "tree_size": merkle_tree_size,
            "root": _b64(merkle_root),
        },
    }
    from axiom.services.crypto.canonical_json import canonicalize

    canonical_bytes = canonicalize(signed_body)

    # Recompute the evidence envelope hash defined by Stage 5 (Evidence):
    #   payload_hash = sha256(nonce || ciphertext || key_id.encode("utf-8"))
    # This proves the stored evidence is byte-for-byte what was signed and
    # Merkle-anchored, without decrypting it. Fails closed when any component
    # is missing — an unverifiable receipt is not a verified one.
    if (
        receipt.evidence_nonce is None
        or receipt.evidence_ciphertext is None
        or not receipt.evidence_key_id
    ):
        payload_hash_matches = False
    else:
        _hasher = hashlib.sha256()
        _hasher.update(receipt.evidence_nonce)
        _hasher.update(receipt.evidence_ciphertext)
        _hasher.update(receipt.evidence_key_id.encode("utf-8"))
        payload_hash_matches = _hasher.digest() == receipt.payload_hash

    if receipt.ed25519_key_id != keys.ed25519_key_id:
        ed_valid = False
    else:
        ed_valid = ed25519.verify(keys.ed25519_public, canonical_bytes, receipt.ed25519_signature)
    if receipt.ml_dsa_key_id != keys.ml_dsa_key_id:
        ml_valid = False
    else:
        ml_valid = ml_dsa.verify(keys.ml_dsa_public, canonical_bytes, receipt.ml_dsa_signature)

    verified = bool(ed_valid and ml_valid and merkle_valid and payload_hash_matches)

    return VerifyResponse(
        receipt_id=receipt.id,
        verified=verified,
        algorithm=receipt.algorithm,
        signed_at=receipt.created_at,
        payload_hash=_b64(receipt.payload_hash),
        merkle_root=_b64(merkle_root),
        merkle_tree_size=merkle_tree_size,
        inclusion_proof=InclusionProofSchema(
            leaf_index=leaf_index if leaf_index is not None else -1,
            tree_size=merkle_tree_size,
            path=[_b64(p) for p in audit_path],
        ),
        verification_details=VerificationDetails(
            ed25519_signature_valid=ed_valid,
            ml_dsa_signature_valid=ml_valid,
            merkle_inclusion_valid=merkle_valid,
            payload_hash_matches=payload_hash_matches,
        ),
        project_id=execution.project_id,
        policy_id=execution.policy_id,
        policy_version=execution.policy_version,
        verdict=Verdict(execution.verdict),
        ed25519_key_id=receipt.ed25519_key_id,
        ml_dsa_key_id=receipt.ml_dsa_key_id,
        ed25519_public_pem=keys.ed25519_public,
        ml_dsa_public_b64=_b64(keys.ml_dsa_public),
    )
