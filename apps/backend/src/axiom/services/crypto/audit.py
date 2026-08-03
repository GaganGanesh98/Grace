"""Crypto operation audit logger. Records WHAT was done, never the key material itself."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

logger = structlog.get_logger("axiom.crypto.audit")


def log_sign(
    algorithm: str,
    key_id: str,
    message_hash: str,
    *,
    success: bool,
    duration_ms: float,
) -> None:
    """Log a signing operation. Never logs raw key or message content."""
    logger.info(
        "crypto.sign",
        algorithm=algorithm,
        key_id=key_id,
        message_hash_prefix=message_hash[:16],
        success=success,
        duration_ms=round(duration_ms, 2),
        timestamp=datetime.now(UTC).isoformat(),
    )


def log_verify(
    algorithm: str,
    key_id: str | None,
    *,
    success: bool,
    duration_ms: float,
) -> None:
    """Log a verification operation."""
    logger.info(
        "crypto.verify",
        algorithm=algorithm,
        key_id=key_id or "unknown",
        success=success,
        duration_ms=round(duration_ms, 2),
        timestamp=datetime.now(UTC).isoformat(),
    )


def log_encrypt(key_id: str, plaintext_size: int, *, success: bool) -> None:
    """Log an encryption operation. Only logs size, never content."""
    logger.info(
        "crypto.encrypt",
        key_id=key_id,
        plaintext_bytes=plaintext_size,
        success=success,
        timestamp=datetime.now(UTC).isoformat(),
    )


def log_key_event(
    event: str,
    key_id: str,
    algorithm: str,
    reason: str | None = None,
) -> None:
    """Log key lifecycle events: generation, rotation, deprecation, revocation."""
    logger.info(
        f"crypto.key.{event}",
        key_id=key_id,
        algorithm=algorithm,
        reason=reason,
        timestamp=datetime.now(UTC).isoformat(),
    )


def log_tsa_attempt(
    tsa_name: str,
    *,
    success: bool,
    status: str | None,
    duration_ms: float,
) -> None:
    """Log a trusted timestamp request (RFC 3161). Never logs the hashed message."""
    logger.info(
        "crypto.timestamp",
        tsa_name=tsa_name,
        success=success,
        status=status,
        duration_ms=round(duration_ms, 2),
        timestamp=datetime.now(UTC).isoformat(),
    )
