"""Crypto utility functions — timing-safe operations and memory scrubbing."""

import ctypes
import hmac


def constant_time_compare(a: bytes, b: bytes) -> bool:
    """Compare two byte strings in constant time. Prevents timing attacks."""
    if not isinstance(a, bytes) or not isinstance(b, bytes):
        return False
    return hmac.compare_digest(a, b)


def zero_memory(data: bytearray) -> None:
    """Overwrite a bytearray with zeros. Best-effort memory scrub for key material."""
    if isinstance(data, bytearray) and len(data) > 0:
        ctypes.memset((ctypes.c_char * len(data)).from_buffer(data), 0, len(data))


def validate_bytes(
    value: object,
    name: str,
    *,
    exact_len: int | None = None,
    min_len: int | None = None,
) -> bytes:
    """Validate bytes: non-empty, optional exact/min length. Raises CryptoInputError."""
    from .exceptions import CryptoInputError

    if not isinstance(value, (bytes, bytearray)):
        raise CryptoInputError(f"{name} must be bytes, got {type(value).__name__}")
    if len(value) == 0:
        raise CryptoInputError(f"{name} must not be empty")
    if exact_len is not None and len(value) != exact_len:
        raise CryptoInputError(f"{name} must be exactly {exact_len} bytes, got {len(value)}")
    if min_len is not None and len(value) < min_len:
        raise CryptoInputError(f"{name} must be at least {min_len} bytes, got {len(value)}")
    return bytes(value)
