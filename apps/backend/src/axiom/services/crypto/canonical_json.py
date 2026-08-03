"""RFC 8785 JSON Canonicalization Scheme (JCS) for deterministic signing payloads."""

from __future__ import annotations

import json
from typing import Any

import rfc8785

type JSONValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class NonCanonicalizableError(ValueError):
    """Raised when a value cannot be represented in RFC 8785 canonical JSON."""


def canonicalize(data: JSONValue) -> bytes:
    """Serialize a JSON-compatible value to RFC 8785 canonical bytes.

    Uses UTF-8, sorted keys at every nesting level, minimal whitespace,
    normalized numbers per RFC 8785 §3.2.

    Raises:
        NonCanonicalizableError: if `data` contains non-finite floats or other
            values that cannot be represented in JCS.
        TypeError: if `data` contains non-JSON-serializable values (for example ``bytes``).
    """
    if isinstance(data, bytes | bytearray):
        raise TypeError("bytes-like values are not JSON-compatible for canonicalization")
    try:
        return rfc8785.dumps(data)
    except (
        rfc8785.FloatDomainError,
        rfc8785.IntegerDomainError,
        rfc8785.CanonicalizationError,
    ) as exc:
        raise NonCanonicalizableError(str(exc)) from exc


def verify_canonical(data: bytes) -> bool:
    """Return True iff `data` is already in RFC 8785 canonical form."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    try:
        return canonicalize(parsed) == data
    except (NonCanonicalizableError, TypeError):
        return False
