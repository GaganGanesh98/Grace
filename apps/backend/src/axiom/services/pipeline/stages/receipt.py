"""Stage 6 (Receipt): sign the payload, append to the Merkle tree, persist.

All three rows (Execution, Receipt, MerkleNode) are committed atomically via
the caller's session. If any step fails the whole request rolls back cleanly.

The signed object is the canonical JSON of:

    {"algorithm": "ed25519+ml-dsa-65",
     "payload_hash": "<base64 sha256>",
     "key_ids": {"ed25519": "<hex>", "ml_dsa": "<hex>"},
     "evidence_key_id": "...",
     "merkle": {"leaf_index": int, "tree_size": int, "root": "<base64>"}}

That's enough for an offline verifier (50-line Python script) to re-run the
signature check AND the Merkle inclusion check.
"""

from __future__ import annotations

import base64
import secrets
import time
from typing import Any

from pydantic import SecretBytes, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.execution import Execution
from axiom.models.receipt import Receipt
from axiom.services.crypto.hybrid_signer import sign_hybrid
from axiom.services.pipeline.protocols import PipelineContext, StageResult
from axiom.services.receipt.merkle_append import MerkleAppender


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _new_receipt_id() -> str:
    return "rcpt_" + secrets.token_urlsafe(16)


def _new_execution_id() -> str:
    return "exec_" + secrets.token_urlsafe(16)


class ReceiptStage:
    name = "receipt"

    def __init__(
        self,
        session: AsyncSession,
        *,
        ed25519_private: SecretStr,
        ed25519_public: str,
        ml_dsa_private: SecretBytes,
        ml_dsa_public: bytes,
        merkle_appender: MerkleAppender | None = None,
    ) -> None:
        self._session = session
        self._ed_priv = ed25519_private
        self._ed_pub = ed25519_public
        self._ml_priv = ml_dsa_private
        self._ml_pub = ml_dsa_public
        self._appender = merkle_appender or MerkleAppender()

    async def execute(self, ctx: PipelineContext) -> StageResult:
        start = time.monotonic()
        if ctx.payload_hash is None or ctx.decision is None:
            return StageResult(
                ok=False,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                error="receipt_without_evidence_or_decision",
            )

        try:
            receipt_id = _new_receipt_id()
            execution_id = _new_execution_id()

            leaf_index, root, tree_size, audit_path = await self._appender.append(
                self._session,
                project_id=ctx.project_id,
                receipt_id=receipt_id,
                payload_hash=ctx.payload_hash,
            )

            signed_body: dict[str, Any] = {
                "algorithm": "ed25519+ml-dsa-65",
                "receipt_id": receipt_id,
                "payload_hash": _b64(ctx.payload_hash),
                "evidence_key_id": ctx.evidence_key_id or "",
                "merkle": {
                    "leaf_index": leaf_index,
                    "tree_size": tree_size,
                    "root": _b64(root),
                },
            }
            signature = sign_hybrid(
                signed_body,
                ed25519_private=self._ed_priv,
                ed25519_public=self._ed_pub,
                ml_dsa_private=self._ml_priv,
                ml_dsa_public=self._ml_pub,
            )

            decision = ctx.decision
            self._session.add(
                Execution(
                    id=execution_id,
                    project_id=ctx.project_id,
                    agent_id=ctx.agent_id,
                    policy_id=decision.policy_id,
                    policy_version=decision.policy_version,
                    action=ctx.action,
                    verdict=decision.verdict.value,
                    rule_id=decision.rule_id,
                    modification=decision.modification,
                    escalation_target=decision.escalation_target,
                    reasoning=decision.reasoning,
                    mode=ctx.mode.value,
                    correlation_id=ctx.correlation_id,
                )
            )
            self._session.add(
                Receipt(
                    id=receipt_id,
                    execution_id=execution_id,
                    payload_hash=ctx.payload_hash,
                    ed25519_signature=signature.ed25519_signature,
                    ed25519_key_id=signature.ed25519_key_id,
                    ml_dsa_signature=signature.ml_dsa_signature,
                    ml_dsa_key_id=signature.ml_dsa_key_id,
                    algorithm=signature.algorithm,
                    merkle_root=root,
                    merkle_tree_size=tree_size,
                    evidence_nonce=ctx.evidence_nonce,
                    evidence_ciphertext=ctx.evidence_ciphertext,
                    evidence_key_id=ctx.evidence_key_id,
                )
            )
            # Flush Execution + Receipt first so the FK target exists before
            # MerkleNode is inserted. Receipt.id is a user-assigned Text PK,
            # so SQLAlchemy's default topological sort doesn't always order
            # them correctly across tables.
            await self._session.flush()
            await self._appender.persist_leaf(
                self._session,
                project_id=ctx.project_id,
                leaf_index=leaf_index,
                leaf_hash=ctx.payload_hash,
                receipt_id=receipt_id,
            )
            await self._session.flush()
        except Exception as exc:  # noqa: BLE001 - fail-closed, runner handles
            return StageResult(
                ok=False,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                error=f"receipt_failed: {type(exc).__name__}: {str(exc)[:500]}",
            )

        ctx.receipt_id = receipt_id
        ctx.execution_id = execution_id
        ctx.signature = signature
        ctx.merkle_leaf_index = leaf_index
        ctx.merkle_leaf_hash = ctx.payload_hash
        ctx.merkle_root = root
        ctx.merkle_tree_size = tree_size
        ctx.merkle_audit_path = audit_path

        return StageResult(
            ok=True,
            stage_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
            data={
                "receipt_id": receipt_id,
                "leaf_index": leaf_index,
                "tree_size": tree_size,
            },
        )
