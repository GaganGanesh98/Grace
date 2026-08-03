"""Tests for PreflightCache."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from axiom.services.preflight.cache import PreflightCache


def _params() -> dict[str, str]:
    return {
        "project_id": "p1",
        "policy_id": "pol",
        "policy_version": "1",
        "agent_id": "a1",
        "api_key_id": "k1",
        "action_canonical_hash_hex": "ab" * 32,
        "mode": "enforce",
    }


def test_cache_key_is_deterministic() -> None:
    p = _params()
    k1 = PreflightCache._compute_key(**p)
    k2 = PreflightCache._compute_key(**p)
    assert k1 == k2
    assert k1.startswith("preflight:v1:")


def test_cache_key_differs_for_different_inputs() -> None:
    base = _params()
    k0 = PreflightCache._compute_key(**base)
    for field in base:
        alt = {**base, field: base[field] + "_x"}
        assert PreflightCache._compute_key(**alt) != k0


@pytest.mark.asyncio
async def test_cache_set_then_get_roundtrip() -> None:
    from axiom.services.redis_client import get_redis

    cache = PreflightCache(get_redis(), ttl_seconds=3600)
    p = _params()
    await cache.set(
        **p,
        prediction_data={
            "predicted_verdict": "approve",
            "rule_id": "r",
            "policy_id": p["policy_id"],
            "policy_version": p["policy_version"],
            "reasoning": "x",
            "explanation": "y",
            "probably_definitive": True,
        },
    )
    got = await cache.get(**p)
    assert got is not None
    pred, age = got
    assert pred.predicted_verdict == "approve"
    assert pred.rule_id == "r"
    assert age >= 0


@pytest.mark.asyncio
async def test_cache_get_miss_returns_none() -> None:
    from axiom.services.redis_client import get_redis

    cache = PreflightCache(get_redis())
    assert await cache.get(**_params()) is None


@pytest.mark.asyncio
async def test_cache_get_malformed_json_returns_none() -> None:
    from axiom.services.redis_client import get_redis

    redis = get_redis()
    cache = PreflightCache(redis)
    key = PreflightCache._compute_key(**_params())
    await redis.set(key, "not-json{{{")
    assert await cache.get(**_params()) is None


@pytest.mark.asyncio
async def test_cache_respects_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    from axiom.services.redis_client import get_redis

    cache = PreflightCache(get_redis(), ttl_seconds=1)
    p = _params()
    await cache.set(
        **p,
        prediction_data={
            "predicted_verdict": "deny",
            "rule_id": None,
            "policy_id": p["policy_id"],
            "policy_version": p["policy_version"],
            "reasoning": "r",
            "explanation": "e",
            "probably_definitive": True,
        },
    )
    assert await cache.get(**p) is not None
    import asyncio

    await asyncio.sleep(2.5)
    assert await cache.get(**p) is None


@pytest.mark.asyncio
async def test_cache_get_redis_error_returns_none() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(side_effect=OSError("redis down"))
    cache = PreflightCache(redis)
    assert await cache.get(**_params()) is None


@pytest.mark.asyncio
async def test_cache_set_redis_error_silent() -> None:
    redis = MagicMock()
    redis.setex = AsyncMock(side_effect=OSError("redis down"))
    cache = PreflightCache(redis)
    await cache.set(
        **_params(),
        prediction_data={
            "predicted_verdict": "approve",
            "rule_id": None,
            "policy_id": "pol",
            "policy_version": "1",
            "reasoning": "r",
            "explanation": "e",
            "probably_definitive": True,
        },
    )


def test_cache_key_contains_no_pii() -> None:
    action_hash_hex = "00" * 32
    key = PreflightCache._compute_key(
        project_id="proj",
        policy_id="pol",
        policy_version="1",
        agent_id="agent",
        api_key_id="key",
        action_canonical_hash_hex=action_hash_hex,
        mode="enforce",
    )
    assert "user@example.com" not in key
    assert "secret" not in key
    assert key.count(":") == 2  # prefix preflight:v1: + hex digest (no colons)
    assert len(key) == len("preflight:v1:") + 64


@pytest.mark.asyncio
async def test_cache_get_naive_cached_at_gets_utc_assigned() -> None:
    from axiom.services.redis_client import get_redis

    redis = get_redis()
    cache = PreflightCache(redis)
    p = _params()
    await redis.set(
        PreflightCache._compute_key(**p),
        json.dumps(
            {
                "predicted_verdict": "approve",
                "rule_id": None,
                "policy_id": p["policy_id"],
                "policy_version": p["policy_version"],
                "reasoning": "r",
                "explanation": "e",
                "probably_definitive": True,
                "cached_at": "2020-01-01T00:00:00",
            }
        ),
    )
    got = await cache.get(**p)
    assert got is not None
    pred, age = got
    assert pred.cached_at.tzinfo is not None
    assert age >= 0


@pytest.mark.asyncio
async def test_cache_invalid_payload_missing_fields() -> None:
    from axiom.services.redis_client import get_redis

    redis = get_redis()
    cache = PreflightCache(redis)
    key = PreflightCache._compute_key(**_params())
    await redis.set(key, json.dumps({"predicted_verdict": "approve"}))
    assert await cache.get(**_params()) is None
