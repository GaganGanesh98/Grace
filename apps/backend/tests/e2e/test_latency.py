"""/v1/govern P95 latency benchmark.

Phase 2 target: < 250ms P95 on local hardware with N < 50 pre-existing leaves.

Skipped under coverage instrumentation: coverage adds ~3-5x overhead which
inflates timings beyond the budget. Run with ``pytest --no-cov tests/e2e/test_latency.py``
to gate on latency.
"""

from __future__ import annotations

import os
import sys
import time

import pytest
from httpx import AsyncClient

from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _coverage_active() -> bool:
    """Heuristic: pytest-cov sets these; sys.gettrace is also set under ctracer."""
    if "COV_CORE_SOURCE" in os.environ or "COVERAGE_RUN" in os.environ:
        return True
    tracer = sys.gettrace()
    if tracer is None:
        return False
    module = getattr(type(tracer), "__module__", "") or ""
    return "coverage" in module


@pytest.mark.skipif(_coverage_active(), reason="coverage instrumentation skews latency")
@pytest.mark.asyncio
async def test_govern_p95_latency_under_250ms(client: AsyncClient) -> None:
    rules = [{"id": "ok", "description": "ok", "when": {"type": "chat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    headers = _auth(fx["api_key_full"])
    agent_id = fx["agent_id"]

    for _ in range(3):
        await client.post(
            "/v1/govern",
            headers=headers,
            json={"action": {"type": "chat", "body": "warmup"}, "agent_id": agent_id},
        )

    n_samples = 25
    samples: list[float] = []
    for i in range(n_samples):
        start = time.monotonic()
        r = await client.post(
            "/v1/govern",
            headers=headers,
            json={"action": {"type": "chat", "body": f"msg-{i}"}, "agent_id": agent_id},
        )
        samples.append((time.monotonic() - start) * 1000)
        assert r.status_code == 200

    samples.sort()
    p95 = samples[int(n_samples * 0.95) - 1]
    p99 = samples[-1]
    print(f"\ngovern p50={samples[n_samples // 2]:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms")
    assert p95 < 250, f"P95 {p95:.1f}ms exceeds 250ms target"
