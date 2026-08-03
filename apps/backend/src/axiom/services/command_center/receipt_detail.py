"""Assemble Command Center receipt detail (Phase 7.2) from governance rows."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any

from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.services.governance.verification import verify_sealed_governance_receipt_from_db


def _preview(obj: object, limit: int = 100) -> str:
    text = json.dumps(obj, default=str, separators=(",", ":")) if obj is not None else ""
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def build_command_center_receipt_detail(
    *,
    receipt: GovernanceReceipt,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
) -> dict[str, Any]:
    """Shape matches Phase 7.2 GET /v1/receipts contract for the dashboard drawer."""
    proof = receipt.merkle_proof if isinstance(receipt.merkle_proof, dict) else {}
    path = proof.get("path") if isinstance(proof.get("path"), list) else []
    depth = len(path)
    leaf_index = proof.get("leaf_index")
    root_hex = receipt.merkle_root.hex() if receipt.merkle_root else ""

    ed_ok = False
    ml_ok = False
    if receipt.status == "sealed":
        vres = verify_sealed_governance_receipt_from_db(receipt, intent, verdict)
        chk = vres.checks if isinstance(vres.checks, dict) else {}
        ed_ok = bool(chk.get("ed25519"))
        ml_ok = bool(chk.get("ml_dsa_65"))
    else:
        ed_ok = receipt.ed25519_sig is not None
        ml_ok = receipt.ml_dsa_sig is not None

    ed_b64 = base64.b64encode(receipt.ed25519_sig).decode("ascii") if receipt.ed25519_sig else ""
    ml_b64 = base64.b64encode(receipt.ml_dsa_sig).decode("ascii") if receipt.ml_dsa_sig else ""

    exec_data = receipt.execution_data if isinstance(receipt.execution_data, dict) else {}
    tsa_raw = exec_data.get("tsa") if isinstance(exec_data.get("tsa"), dict) else {}
    tsa = {
        "timestamp": tsa_raw.get("timestamp"),
        "verified": bool(tsa_raw.get("verified", False)),
        "authority": tsa_raw.get("authority") or "—",
    }

    pipeline: list[dict[str, Any]] = [
        {
            "stage": 1,
            "name": "intent",
            "outcome": "recorded",
            "evidence": {"action_type": intent.action_type, "target": intent.target},
        },
        {
            "stage": 2,
            "name": "risk",
            "outcome": str(verdict.risk_assessed or "—"),
            "evidence": verdict.context if isinstance(verdict.context, dict) else {},
        },
        {
            "stage": 3,
            "name": "policy",
            "outcome": f"policy {verdict.policy_version}",
            "evidence": {"rules_evaluated": verdict.rules_evaluated},
        },
        {
            "stage": 4,
            "name": "authority",
            "outcome": str(verdict.verdict),
            "evidence": {"reason": verdict.reason},
        },
        {
            "stage": 5,
            "name": "evidence",
            "outcome": "redacted and persisted" if exec_data else "pending",
            "evidence": exec_data,
        },
        {
            "stage": 6,
            "name": "receipt",
            "outcome": "dual-signed and anchored" if receipt.status == "sealed" else "pending seal",
            "evidence": {
                "status": receipt.status,
                "sealed_at": receipt.sealed_at.isoformat() if receipt.sealed_at else None,
            },
        },
    ]

    ts = receipt.sealed_at or receipt.created_at
    ts_iso = ts.isoformat() if isinstance(ts, datetime) else ""

    return {
        "receipt_id": str(receipt.id),
        "verdict": str(verdict.verdict),
        "action_type": intent.action_type,
        "timestamp": ts_iso,
        "signatures": {
            "ed25519": {"signature": ed_b64, "verified": ed_ok},
            "ml_dsa_65": {"signature": ml_b64, "verified": ml_ok},
        },
        "merkle": {
            "leaf_index": leaf_index,
            "depth": depth,
            "root_hash": f"0x{root_hex}" if root_hex else "",
        },
        "tsa": tsa,
        "pipeline": pipeline,
        "request_preview": _preview(intent.parameters),
        "response_preview": _preview(
            exec_data.get("upstream_audit") if isinstance(exec_data, dict) else exec_data
        ),
    }


__all__ = ["build_command_center_receipt_detail"]
