"""Stage 6: declared intent vs reported execution; public POST /verify crypto checks."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.schemas.governance import GovernanceEngineVerifyResponse, VerifyReceiptRequest
from axiom.services.crypto import ed25519, ml_dsa
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.crypto.merkle import InclusionProof, verify_inclusion


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    mismatches: list[dict[str, Any]]
    status: str


def verify_execution(
    intent: GovernanceIntent,
    execution_data: dict[str, Any],
) -> VerificationResult:
    if not execution_data:
        return VerificationResult(passed=True, mismatches=[], status="skipped")

    mismatches: list[dict[str, Any]] = []

    exp_target = intent.target
    act_target = execution_data.get("target")
    if act_target != exp_target:
        mismatches.append({"field": "target", "expected": exp_target, "actual": act_target})

    exp_action = intent.action_type
    act_action = execution_data.get("action_type")
    if act_action != exp_action:
        mismatches.append({"field": "action_type", "expected": exp_action, "actual": act_action})

    exp_risk = intent.risk_declared
    act_risk = execution_data.get("risk")
    if act_risk is not None and str(act_risk) != str(exp_risk):
        mismatches.append({"field": "risk", "expected": exp_risk, "actual": act_risk})

    passed = len(mismatches) == 0
    return VerificationResult(
        passed=passed,
        mismatches=mismatches,
        status="pass" if passed else "fail",
    )


def verify_receipt_independent(body: VerifyReceiptRequest) -> GovernanceEngineVerifyResponse:  # noqa: PLR0915
    """Ed25519, ML-DSA-65, and Merkle checks (no database)."""
    errors: list[str] = []
    checks: dict[str, bool] = {"ed25519": False, "ml_dsa_65": False, "merkle": False}
    try:
        parsed = json.loads(body.receipt_json)
    except json.JSONDecodeError:
        return GovernanceEngineVerifyResponse(
            valid=False,
            checks=checks,
            errors=["receipt_json is not valid JSON"],
        )
    if not isinstance(parsed, dict):
        return GovernanceEngineVerifyResponse(
            valid=False,
            checks=checks,
            errors=["receipt_json must be a JSON object"],
        )
    try:
        canonical = canonicalize(parsed)
    except (TypeError, ValueError) as exc:
        return GovernanceEngineVerifyResponse(
            valid=False,
            checks=checks,
            errors=[f"canonicalization failed: {exc}"],
        )

    try:
        ed_sig = base64.b64decode(body.ed25519_signature, validate=True)
    except (ValueError, TypeError, binascii.Error):
        return GovernanceEngineVerifyResponse(
            valid=False,
            checks=checks,
            errors=["invalid ed25519_signature base64"],
        )

    pk_text = body.ed25519_public_key.strip()
    try:
        if "BEGIN" in pk_text:
            checks["ed25519"] = bool(ed25519.verify(pk_text, canonical, ed_sig))
        else:
            raw_pk = base64.b64decode(pk_text, validate=True)
            checks["ed25519"] = bool(ed25519.verify(canonical, ed_sig, raw_pk))
    except (ValueError, TypeError, binascii.Error):
        errors.append("ed25519 verification could not run")
        checks["ed25519"] = False

    if body.ml_dsa_signature and body.ml_dsa_public_key:
        try:
            ml_sig = base64.b64decode(body.ml_dsa_signature, validate=True)
            ml_pub = base64.b64decode(body.ml_dsa_public_key, validate=True)
            checks["ml_dsa_65"] = bool(ml_dsa.verify(ml_pub, canonical, ml_sig))
        except (ValueError, TypeError, binascii.Error):
            errors.append("ML-DSA verify failed")
            checks["ml_dsa_65"] = False
    else:
        checks["ml_dsa_65"] = True

    leaf_digest = hashlib.sha256(canonical).digest()
    try:
        root = bytes.fromhex(body.merkle_root)
    except ValueError:
        errors.append("invalid merkle_root hex")
        return GovernanceEngineVerifyResponse(valid=False, checks=checks, errors=errors)

    leaf_index = body.leaf_index
    tree_size = body.tree_size
    path_hex = list(body.merkle_proof)
    merkle_obj = parsed.get("merkle")
    if isinstance(merkle_obj, dict):
        if leaf_index is None and merkle_obj.get("leaf_index") is not None:
            leaf_index = int(merkle_obj["leaf_index"])
        if tree_size is None and merkle_obj.get("tree_size") is not None:
            tree_size = int(merkle_obj["tree_size"])
        if not path_hex and isinstance(merkle_obj.get("path"), list):
            path_hex = [str(x) for x in merkle_obj["path"]]

    if leaf_index is None or tree_size is None:
        errors.append("merkle leaf_index and tree_size are required for inclusion proof")
        checks["merkle"] = False
    else:
        try:
            path = tuple(bytes.fromhex(h) for h in path_hex)
            proof = InclusionProof(
                leaf_index=leaf_index,
                tree_size=tree_size,
                path=path,
            )
            preimage = leaf_digest
            if body.leaf_preimage_hex:
                preimage = bytes.fromhex(body.leaf_preimage_hex)
            checks["merkle"] = bool(verify_inclusion(root, preimage, proof))
        except (ValueError, TypeError):
            errors.append("merkle proof verification failed")
            checks["merkle"] = False

    valid = bool(checks["ed25519"] and checks["ml_dsa_65"] and checks["merkle"])
    return GovernanceEngineVerifyResponse(valid=valid, checks=checks, errors=errors)


def verify_sealed_governance_receipt_from_db(
    receipt: GovernanceReceipt,
    intent: GovernanceIntent,
    verdict: GovernanceVerdict,
) -> GovernanceEngineVerifyResponse:
    """Build the independent verify payload from DB rows and run crypto checks."""
    from axiom.services.governance.receipt import (
        approval_dict_from_receipt,
        unsigned_receipt_for_sealing,
    )
    from axiom.services.receipt.keys import get_signing_keys

    payload_obj = unsigned_receipt_for_sealing(
        receipt_id=str(receipt.id),
        intent=intent,
        verdict=verdict,
        execution_data=receipt.execution_data,
        verification_status=receipt.verification or "",
        mismatches=list(receipt.mismatches or []),
        executed_at=receipt.executed_at,
        approval=approval_dict_from_receipt(receipt),
    )
    receipt_json = canonicalize(payload_obj).decode("utf-8")
    ed_b64 = base64.b64encode(receipt.ed25519_sig).decode("ascii") if receipt.ed25519_sig else ""
    ml_b64 = base64.b64encode(receipt.ml_dsa_sig).decode("ascii") if receipt.ml_dsa_sig else ""
    mp = receipt.merkle_proof if isinstance(receipt.merkle_proof, dict) else {}
    raw_path = mp.get("path") if isinstance(mp.get("path"), list) else []
    path = [str(x) for x in raw_path]
    merkle_root_hex = receipt.merkle_root.hex() if receipt.merkle_root else ""
    keys = get_signing_keys()
    leaf_index = mp.get("leaf_index")
    tree_size = mp.get("tree_size")
    body = VerifyReceiptRequest(
        receipt_json=receipt_json,
        ed25519_signature=ed_b64,
        ml_dsa_signature=ml_b64,
        merkle_proof=path,
        merkle_root=merkle_root_hex,
        ed25519_public_key=keys.ed25519_public,
        ml_dsa_public_key=base64.b64encode(keys.ml_dsa_public).decode("ascii"),
        leaf_index=int(leaf_index) if leaf_index is not None else None,
        tree_size=int(tree_size) if tree_size is not None else None,
    )
    return verify_receipt_independent(body)
