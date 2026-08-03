"""Forensic audit fields attached to every governed proxy receipt.

All helpers are best-effort and MUST NOT raise. Bodies may contain PII —
only hashes and parsed scalars are returned. Failures return ``None``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def sha256_hex(data: bytes | None) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _try_parse_json(data: bytes | None) -> dict[str, Any] | None:
    if not data:
        return None
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_model_from_request(body: bytes | None) -> str | None:
    """Return ``model`` field from the request JSON, or None."""
    data = _try_parse_json(body)
    if data is None:
        return None
    model = data.get("model")
    return str(model) if isinstance(model, (str, int, float)) else None


def parse_token_usage(body: bytes | None) -> dict[str, int] | None:
    """Normalize OpenAI-compatible and Anthropic usage shapes. Return None on miss."""
    data = _try_parse_json(body)
    if data is None:
        return None
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None

    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if isinstance(prompt, int) and isinstance(completion, int):
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total if isinstance(total, int) else prompt + completion,
        }

    # Anthropic shape: {"input_tokens": X, "output_tokens": Y}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        return {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    return None


def build_upstream_audit(
    *,
    request_body: bytes | None,
    response_body: bytes | None,
    response_hash_hex: str | None,
    upstream_provider: str,
    upstream_status: int,
    upstream_latency_ms: int,
    vault_key_id: UUID | None,
) -> dict[str, Any]:
    """Compose the full audit dict nested under execution_data.upstream_audit.

    ``response_hash_hex`` lets streaming callers pass a pre-computed streaming hash
    and leave ``response_body=None`` to avoid keeping the full buffer in memory.
    """
    return {
        "request_hash": sha256_hex(request_body),
        "response_hash": response_hash_hex
        if response_hash_hex is not None
        else sha256_hex(response_body),
        "upstream_provider": upstream_provider,
        "upstream_model": parse_model_from_request(request_body),
        "upstream_status": upstream_status,
        "upstream_latency_ms": upstream_latency_ms,
        "token_usage": parse_token_usage(response_body),
        "vault_key_id": str(vault_key_id) if vault_key_id is not None else None,
    }
