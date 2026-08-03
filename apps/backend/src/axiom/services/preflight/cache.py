"""PreflightCache — Redis-backed prediction cache.

Key schema: "preflight:v1:{sha256_hex}"
  where sha256_hex = SHA-256 of canonical JSON of {
    "project_id": str,
    "policy_id": str,
    "policy_version": str,
    "agent_id": str,
    "api_key_id": str,
    "action_canonical_hash": str (hex sha256 of the canonical action bytes),
    "mode": "shadow" | "enforce"
  }

Value schema (JSON):
  {
    "predicted_verdict": "approve" | "deny" | "modify" | "escalate",
    "rule_id": str | null,
    "policy_id": str,
    "policy_version": str,
    "reasoning": str,
    "explanation": str,
    "probably_definitive": bool,
    "cached_at": iso8601 utc str
  }

TTL: configurable via Settings.preflight_cache_ttl_seconds (default 3600).

Failure mode: any Redis error → log warning, return None (cache miss). Never raises.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.asyncio import Redis

from axiom.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CachedPrediction:
    predicted_verdict: str
    rule_id: str | None
    policy_id: str
    policy_version: str
    reasoning: str
    explanation: str
    probably_definitive: bool
    cached_at: datetime


class PreflightCache:
    _KEY_PREFIX = "preflight:v1:"

    def __init__(self, redis_client: Redis, ttl_seconds: int | None = None) -> None:
        self._redis = redis_client
        self._ttl = (
            ttl_seconds if ttl_seconds is not None else get_settings().preflight_cache_ttl_seconds
        )

    @staticmethod
    def _compute_key(
        project_id: str,
        policy_id: str,
        policy_version: str,
        agent_id: str,
        api_key_id: str,
        action_canonical_hash_hex: str,
        mode: str,
    ) -> str:
        canonical = json.dumps(
            {
                "project_id": project_id,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "agent_id": agent_id,
                "api_key_id": api_key_id,
                "action_canonical_hash": action_canonical_hash_hex,
                "mode": mode,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return PreflightCache._KEY_PREFIX + hashlib.sha256(canonical.encode()).hexdigest()

    async def get(
        self,
        project_id: str,
        policy_id: str,
        policy_version: str,
        agent_id: str,
        api_key_id: str,
        action_canonical_hash_hex: str,
        mode: str,
    ) -> tuple[CachedPrediction, int] | None:
        """Returns (prediction, age_seconds) on hit, None on miss."""
        key = self._compute_key(
            project_id,
            policy_id,
            policy_version,
            agent_id,
            api_key_id,
            action_canonical_hash_hex,
            mode,
        )
        try:
            raw = await self._redis.get(key)
        except Exception:  # noqa: BLE001 — cache is best-effort
            logger.warning("preflight_cache_get_error", key_prefix=self._KEY_PREFIX, exc_info=True)
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            cached_at = datetime.fromisoformat(data["cached_at"])
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=UTC)
            age = int((datetime.now(UTC) - cached_at).total_seconds())
            prediction = CachedPrediction(
                predicted_verdict=data["predicted_verdict"],
                rule_id=data.get("rule_id"),
                policy_id=data["policy_id"],
                policy_version=data["policy_version"],
                reasoning=data["reasoning"],
                explanation=data["explanation"],
                probably_definitive=data["probably_definitive"],
                cached_at=cached_at,
            )
        except (KeyError, ValueError, json.JSONDecodeError):
            logger.warning("preflight_cache_malformed", key=key)
            return None
        return (prediction, age)

    async def set(
        self,
        project_id: str,
        policy_id: str,
        policy_version: str,
        agent_id: str,
        api_key_id: str,
        action_canonical_hash_hex: str,
        mode: str,
        prediction_data: dict[str, Any],
    ) -> None:
        key = self._compute_key(
            project_id,
            policy_id,
            policy_version,
            agent_id,
            api_key_id,
            action_canonical_hash_hex,
            mode,
        )
        value = {
            **prediction_data,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        try:
            await self._redis.setex(key, self._ttl, json.dumps(value))
        except Exception:  # noqa: BLE001
            logger.warning("preflight_cache_set_error", key=key, exc_info=True)
            # Silent degradation: next call will recompute
