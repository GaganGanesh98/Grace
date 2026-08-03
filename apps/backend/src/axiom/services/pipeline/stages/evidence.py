"""Stage 5 (Evidence): build the evidence payload, encrypt it, and hash it.

The evidence payload is the signed thing. Structure:

    {
      "version": "axiom-evidence/1",
      "correlation_id": "...",
      "requested_at": "2026-04-16T17:37:00Z",
      "project_id": "...",
      "agent_id": "...",
      "api_key_id": "...",
      "mode": "shadow" | "enforce",
      "action": <caller action JSON>,
      "policy": {"id": "...", "version": "...", "rule_id": "...", "verdict": "..."},
      "modification": <...> | null,
      "escalation_target": <str> | null,
      "reasoning": "...",
      "explanation": "...",
      "dispatched": true | false,
      "injection_matches": [{"category": "...", "pattern_id": "..."}, ...],
      "stage_timings_ms": [{"name": "intent", "ok": true, "duration_ms": 1.2}, ...]
    }

AES-GCM encrypts the bytes. ``payload_hash`` is the SHA-256 of the ciphertext
plus open metadata (``nonce || ciphertext || key_id``). That hash is what the
Receipt stage feeds into the hybrid signer and into the Merkle leaf.

Fail modes:
  * Canonicalization failure -> StageResult(ok=False).
  * AES-GCM failure -> StageResult(ok=False).
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from typing import Any

from axiom.services.crypto import aes_gcm
from axiom.services.crypto.canonical_json import NonCanonicalizableError, canonicalize
from axiom.services.pipeline.protocols import PipelineContext, StageResult


def _build_evidence_body(ctx: PipelineContext) -> dict[str, Any]:
    decision = ctx.decision
    verdict = decision.verdict.value if decision is not None else "deny"
    return {
        "version": "axiom-evidence/1",
        "correlation_id": ctx.correlation_id,
        "requested_at": ctx.requested_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "finalized_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "project_id": str(ctx.project_id),
        "agent_id": str(ctx.agent_id),
        "api_key_id": str(ctx.api_key_id),
        "mode": ctx.mode.value,
        "action": ctx.action,
        "policy": {
            "id": decision.policy_id if decision else (ctx.policy_id or "UNKNOWN"),
            "version": decision.policy_version if decision else (ctx.policy_version or "0"),
            "rule_id": decision.rule_id if decision else None,
            "verdict": verdict,
        },
        "modification": decision.modification if decision else None,
        "escalation_target": decision.escalation_target if decision else None,
        "reasoning": decision.reasoning if decision else "unknown",
        "explanation": ctx.explanation or "",
        "dispatched": ctx.dispatched,
        "injection_matches": [
            {
                "category": m.category.value,
                "pattern_id": m.pattern_id,
                "span": list(m.matched_span),
            }
            for m in ctx.injection_matches
        ],
        "stage_timings_ms": [
            {
                "name": r.stage_name,
                "ok": r.ok,
                "duration_ms": round(r.duration_ms, 3),
                "error": r.error,
            }
            for r in ctx.stage_results
        ],
    }


class EvidenceStage:
    name = "evidence"

    def __init__(self, evidence_key: bytes, evidence_key_id: str) -> None:
        if len(evidence_key) != 32:
            msg = "evidence key must be 32 bytes (AES-256-GCM)"
            raise ValueError(msg)
        self._key = evidence_key
        self._key_id = evidence_key_id

    async def execute(self, ctx: PipelineContext) -> StageResult:
        start = time.monotonic()
        try:
            body = _build_evidence_body(ctx)
            plaintext = canonicalize(body)
            ciphertext = aes_gcm.encrypt(self._key, plaintext)
            # Hash the publicly-visible envelope: nonce || ciphertext || key_id
            hasher = hashlib.sha256()
            hasher.update(ciphertext.nonce)
            hasher.update(ciphertext.ciphertext)
            hasher.update(self._key_id.encode("utf-8"))
            payload_hash = hasher.digest()
        except (NonCanonicalizableError, TypeError, ValueError) as exc:
            return StageResult(
                ok=False,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                error=f"evidence_build_failed: {type(exc).__name__}: {str(exc)[:200]}",
            )

        ctx.evidence_plaintext = plaintext
        ctx.evidence_nonce = ciphertext.nonce
        ctx.evidence_ciphertext = ciphertext.ciphertext
        ctx.evidence_key_id = self._key_id
        ctx.payload_hash = payload_hash

        return StageResult(
            ok=True,
            stage_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
            data={
                "plaintext_bytes": len(plaintext),
                "ciphertext_bytes": len(ciphertext.ciphertext),
                "payload_hash_hex": payload_hash.hex(),
            },
        )
