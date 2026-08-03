"""Generate portable verification bundles for cross-language verification.

A verification bundle contains everything needed to verify a receipt
in any language (Python, TypeScript, Go, Rust) without AXIOM.
"""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass


@dataclass
class VerificationBundle:
    """Self-contained package for offline receipt verification."""

    receipt_json: str  # The full receipt as JSON
    ed25519_public_key: str  # Base64-encoded public key
    ed25519_signature: str  # Base64-encoded signature
    ml_dsa_public_key: str | None  # Base64-encoded, None if stubbed
    ml_dsa_signature: str | None  # Base64-encoded, None if stubbed
    merkle_proof: list[str]  # List of base64-encoded hashes
    merkle_root: str  # Base64-encoded root hash
    hash_algorithm: str  # "sha-256"
    signature_algorithms: list[str]  # ["ed25519", "ml-dsa-65"]
    verification_instructions: str  # Human-readable verification steps

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @staticmethod
    def verification_steps() -> str:
        return """
OFFLINE RECEIPT VERIFICATION STEPS:

1. Parse receipt_json
2. Compute SHA-256 hash of receipt_json bytes
3. Verify ed25519_signature against hash using ed25519_public_key
4. If ml_dsa_public_key present: verify ml_dsa_signature against hash
5. Verify merkle_proof: starting from SHA-256(receipt_json),
   combine with each proof hash and compare final result to merkle_root
6. All three checks must pass for the receipt to be valid

LIBRARIES BY LANGUAGE:
  Python:   cryptography (Ed25519), hashlib (SHA-256)
  TypeScript: @noble/ed25519, crypto.subtle
  Go:       crypto/ed25519, crypto/sha256
  Rust:     ed25519-dalek, sha2
"""


def create_bundle(
    receipt_json: str,
    ed25519_pub: bytes,
    ed25519_sig: bytes,
    ml_dsa_pub: bytes | None,
    ml_dsa_sig: bytes | None,
    merkle_proof: list[bytes],
    merkle_root: bytes,
) -> VerificationBundle:
    """Create a portable verification bundle from receipt components."""
    return VerificationBundle(
        receipt_json=receipt_json,
        ed25519_public_key=base64.b64encode(ed25519_pub).decode(),
        ed25519_signature=base64.b64encode(ed25519_sig).decode(),
        ml_dsa_public_key=base64.b64encode(ml_dsa_pub).decode() if ml_dsa_pub else None,
        ml_dsa_signature=base64.b64encode(ml_dsa_sig).decode() if ml_dsa_sig else None,
        merkle_proof=[base64.b64encode(h).decode() for h in merkle_proof],
        merkle_root=base64.b64encode(merkle_root).decode(),
        hash_algorithm="sha-256",
        signature_algorithms=["ed25519"] + (["ml-dsa-65"] if ml_dsa_pub else []),
        verification_instructions=VerificationBundle.verification_steps(),
    )
