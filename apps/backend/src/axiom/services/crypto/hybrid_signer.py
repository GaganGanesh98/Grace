"""Hybrid signing: canonical JSON payload + Ed25519 + ML-DSA-65."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from pydantic import SecretBytes, SecretStr

from axiom.services.crypto import canonical_json, ed25519, ml_dsa
from axiom.services.crypto.canonical_json import JSONValue


@dataclass(frozen=True)
class HybridSignature:
    payload_bytes: bytes
    payload_hash: bytes
    ed25519_signature: bytes
    ed25519_key_id: str
    ml_dsa_signature: bytes
    ml_dsa_key_id: str
    algorithm: str = "ed25519+ml-dsa-65"


def sign_hybrid(
    payload: JSONValue,
    ed25519_private: SecretStr,
    ed25519_public: str,
    ml_dsa_private: SecretBytes,
    ml_dsa_public: bytes,
) -> HybridSignature:
    payload_bytes = canonical_json.canonicalize(payload)
    payload_hash = hashlib.sha256(payload_bytes).digest()
    ed_sig = ed25519.sign(ed25519_private, payload_bytes)
    ml_sig = ml_dsa.sign(ml_dsa_private, payload_bytes)
    return HybridSignature(
        payload_bytes=payload_bytes,
        payload_hash=payload_hash,
        ed25519_signature=ed_sig,
        ed25519_key_id=ed25519.stable_key_id(ed25519_public),
        ml_dsa_signature=ml_sig,
        ml_dsa_key_id=ml_dsa.stable_key_id(ml_dsa_public),
    )


def verify_hybrid(
    sig: HybridSignature,
    ed25519_public: str,
    ml_dsa_public: bytes,
    expected_payload: JSONValue,
) -> bool:
    expected_bytes = canonical_json.canonicalize(expected_payload)
    if not hmac.compare_digest(sig.payload_bytes, expected_bytes):
        return False
    if not hmac.compare_digest(hashlib.sha256(sig.payload_bytes).digest(), sig.payload_hash):
        return False
    if not hmac.compare_digest(sig.ed25519_key_id, ed25519.stable_key_id(ed25519_public)):
        return False
    if not hmac.compare_digest(sig.ml_dsa_key_id, ml_dsa.stable_key_id(ml_dsa_public)):
        return False
    if not ed25519.verify(ed25519_public, sig.payload_bytes, sig.ed25519_signature):
        return False
    return ml_dsa.verify(ml_dsa_public, sig.payload_bytes, sig.ml_dsa_signature)
