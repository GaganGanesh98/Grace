"""Latency smoke: preflight P95 targets (best-effort on shared CI)."""

from __future__ import annotations

import time

import pytest
from httpx import AsyncClient

from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _p95_ms(samples: list[float]) -> float:
    s = sorted(samples)
    idx = max(0, int(0.95 * len(s)) - 1)
    return s[idx]


@pytest.mark.asyncio
async def test_preflight_p95_cached_under_target(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "lat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    body = {"action": {"type": "lat"}, "agent_id": fx["agent_id"]}
    h = _auth(fx["api_key_full"])
    await client.post("/v1/preflight", headers=h, json=body)
    times: list[float] = []
    for _ in range(120):
        t0 = time.perf_counter()
        r = await client.post("/v1/preflight", headers=h, json=body)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        if r.json()["cached"]:
            times.append(elapsed_ms)
    assert len(times) >= 80, "expected stable Redis cache hits for identical preflight calls"
    p95 = _p95_ms(times)
    assert p95 < 30.0, f"P95 cached {p95:.1f}ms exceeds 30ms target"


@pytest.mark.asyncio
async def test_preflight_p95_uncached_under_target(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "lat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    h = _auth(fx["api_key_full"])
    times: list[float] = []
    for i in range(40):
        t0 = time.perf_counter()
        r = await client.post(
            "/v1/preflight",
            headers=h,
            json={"action": {"type": "lat", "n": i}, "agent_id": fx["agent_id"]},
        )
        times.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
        assert r.json()["cached"] is False
    p95 = _p95_ms(times)
    assert p95 < 100.0, f"P95 uncached {p95:.1f}ms exceeds 100ms target"
