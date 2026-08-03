"""Outbound webhook client with bounded exponential backoff + jitter (no deps)."""

from __future__ import annotations

import asyncio
import secrets

import httpx
import structlog

logger = structlog.get_logger(__name__)


class EscalationDeliveryError(RuntimeError):
    """The escalation webhook could not be delivered after all retries."""


async def post_with_retry(
    url: str,
    *,
    content: bytes,
    headers: dict[str, str],
    max_attempts: int = 4,
    base_delay: float = 0.5,
    timeout: float = 10.0,
) -> httpx.Response:
    """POST ``content`` to ``url``, retrying transient failures.

    Retries network errors and 5xx responses with exponential backoff + jitter;
    4xx responses are returned immediately (a 4xx is our payload/signature bug,
    not a transient condition). Raises ``EscalationDeliveryError`` if every
    attempt fails.
    """
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(url, content=content, headers=headers)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("escalation.attempt_error", attempt=attempt, error=str(exc))
            else:
                if response.status_code < 500:
                    return response
                last_error = EscalationDeliveryError(f"n8n returned {response.status_code}")
                logger.warning(
                    "escalation.attempt_5xx", attempt=attempt, status=response.status_code
                )

            if attempt < max_attempts:
                # Exponential backoff with jitter in [0, base_delay).
                jitter = secrets.randbelow(1000) / 1000 * base_delay
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)) + jitter)

    raise EscalationDeliveryError(
        f"escalation webhook to {url} failed after {max_attempts} attempts"
    ) from last_error
