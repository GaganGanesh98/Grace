"""HMAC-SHA256 signing/verification for the n8n escalation webhook + callback.

Matches the codebase's existing `hmac.compare_digest` idiom (api_key/service.py).
The signature is computed over the raw request body, so it binds the secret to
the exact bytes n8n received/returns (resistant to tampering).
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Axiom-Signature"


def sign_body(secret: str, body: bytes) -> str:
    """Return ``sha256=<hex hmac>`` for the given body."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, provided: str | None) -> bool:
    """Constant-time-compare the provided signature against the expected one."""
    if not provided:
        return False
    expected = sign_body(secret, body)
    return hmac.compare_digest(expected, provided)
