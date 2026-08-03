"""PreflightService integration-style tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from axiom.db import session_scope
from axiom.models.execution import Execution
from axiom.models.merkle_node import MerkleNode
from axiom.models.policy import Policy
from axiom.models.receipt import Receipt
from axiom.services.pipeline.protocols import PipelineMode
from axiom.services.policy.evaluator import Verdict
from axiom.services.preflight.cache import PreflightCache
from axiom.services.preflight.service import PreflightService
from axiom.services.redis_client import get_redis
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


async def _row_counts() -> tuple[int, int, int]:
    async with session_scope() as session:
        e = await session.scalar(select(func.count()).select_from(Execution))
        r = await session.scalar(select(func.count()).select_from(Receipt))
        m = await session.scalar(select(func.count()).select_from(MerkleNode))
    return int(e or 0), int(r or 0), int(m or 0)


@pytest.mark.asyncio
async def test_predict_cache_miss_then_hit(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "chat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    body = {
        "action": {"type": "chat", "body": "hi"},
        "agent_id": fx["agent_id"],
        "mode": "enforce",
    }
    r1 = await client.post("/v1/preflight", headers=_auth(fx["api_key_full"]), json=body)
    assert r1.status_code == 200, r1.text
    assert r1.json()["cached"] is False
    r2 = await client.post("/v1/preflight", headers=_auth(fx["api_key_full"]), json=body)
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    assert r2.json()["cache_age_seconds"] is not None


@pytest.mark.asyncio
async def test_predict_strategy_error_returns_deny(client: AsyncClient) -> None:
    from axiom.services.pipeline.stages import strategy as strat_mod

    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    from axiom.services.pipeline.protocols import StageResult

    async def boom(self, ctx):
        _ = self, ctx
        return StageResult(ok=False, stage_name="strategy", duration_ms=0.0, error="db down")

    with patch.object(strat_mod.StrategyStage, "execute", boom):
        r = await client.post(
            "/v1/preflight",
            headers=_auth(fx["api_key_full"]),
            json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["predicted_verdict"] == "deny"
    assert "strategy" in data["reasoning"]


@pytest.mark.asyncio
async def test_predict_no_policy_returns_deny(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(
        client,
        policy_rules=[{"id": "a", "description": "d", "when": {"type": "z"}, "then": "approve"}],
    )
    async with session_scope() as session:
        await session.execute(delete(Policy).where(Policy.project_id == UUID(fx["project_id"])))
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "chat"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    assert r.json()["predicted_verdict"] == "deny"
    assert "no policy" in r.json()["reasoning"].lower()


@pytest.mark.asyncio
async def test_predict_intent_error_returns_deny(client: AsyncClient) -> None:
    from axiom.services.pipeline.stages import intent as intent_mod

    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async def bad(self, ctx):
        _ = self, ctx
        from axiom.services.pipeline.protocols import StageResult

        return StageResult(ok=False, stage_name="intent", duration_ms=0.0, error="bad")

    with patch.object(intent_mod.IntentStage, "execute", bad):
        r = await client.post(
            "/v1/preflight",
            headers=_auth(fx["api_key_full"]),
            json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
        )
    assert r.status_code == 200
    assert r.json()["predicted_verdict"] == "deny"


@pytest.mark.asyncio
async def test_predict_authority_error_returns_deny(client: AsyncClient) -> None:
    from axiom.services.pipeline.stages import authority as auth_mod

    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async def bad(self, ctx):
        _ = self, ctx
        from axiom.services.pipeline.protocols import StageResult

        return StageResult(ok=False, stage_name="authority", duration_ms=0.0, error="boom")

    with patch.object(auth_mod.AuthorityStage, "execute", bad):
        r = await client.post(
            "/v1/preflight",
            headers=_auth(fx["api_key_full"]),
            json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
        )
    assert r.status_code == 200
    assert r.json()["predicted_verdict"] == "deny"


@pytest.mark.asyncio
async def test_predict_deterministic_rule_confidence_high_on_miss(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "chat"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "chat"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["cached"] is False
    assert j["confidence"] == "high"
    assert j["probably_definitive"] is True


@pytest.mark.asyncio
async def test_predict_nondeterministic_rule_confidence_medium_on_miss(client: AsyncClient) -> None:
    rules = [
        {
            "id": "age",
            "description": "age gate",
            "when": {"age": {"op": "gt", "value": 10}},
            "then": "approve",
        }
    ]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "x", "age": 20}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["probably_definitive"] is False
    assert j["confidence"] == "medium"


@pytest.mark.asyncio
async def test_predict_unique_prediction_id_per_call(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    ids: set[str] = set()
    for _ in range(20):
        r = await client.post(
            "/v1/preflight",
            headers=_auth(fx["api_key_full"]),
            json={"action": {"type": "t", "k": str(uuid4())}, "agent_id": fx["agent_id"]},
        )
        assert r.status_code == 200
        ids.add(r.json()["prediction_id"])
    assert len(ids) == 20


@pytest.mark.asyncio
async def test_predict_does_not_emit_receipt(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    before = await _row_counts()
    for _ in range(5):
        r = await client.post(
            "/v1/preflight",
            headers=_auth(fx["api_key_full"]),
            json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
        )
        assert r.status_code == 200
    after = await _row_counts()
    assert before == after


@pytest.mark.asyncio
async def test_preflight_service_predict_never_none(client: AsyncClient) -> None:
    """Direct service call returns a prediction object (never None)."""

    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    async with session_scope() as session:
        svc = PreflightService(PreflightCache(get_redis()))
        pred = await svc.predict(
            session=session,
            project_id=UUID(fx["project_id"]),
            agent_id=UUID(fx["agent_id"]),
            api_key_id=UUID(fx["api_key_id"]),
            action={"type": "t"},
            mode=PipelineMode.ENFORCE,
        )
    assert pred.predicted_verdict in {
        Verdict.APPROVE,
        Verdict.DENY,
        Verdict.MODIFY,
        Verdict.ESCALATE,
    }


@pytest.mark.asyncio
async def test_predict_cache_get_raises_swallowed(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "getfail"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async def raise_get(*_a: object, **_k: object) -> None:
        raise RuntimeError("surprise")

    monkeypatch.setattr(PreflightCache, "get", raise_get)
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "getfail"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    assert r.json()["cached"] is False


@pytest.mark.asyncio
async def test_predict_cache_set_failure_still_returns_prediction(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "setfail"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async def boom_set(*_a: object, **_k: object) -> None:
        raise OSError("cache set failed")

    monkeypatch.setattr(PreflightCache, "set", boom_set)
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "setfail"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    assert r.json()["predicted_verdict"] == "approve"


@pytest.mark.asyncio
async def test_lookup_rule_skips_non_dict_and_invalid() -> None:
    svc = PreflightService(PreflightCache(get_redis()))
    session = AsyncMock()
    row = MagicMock()
    row.rules = [
        "not-a-dict",
        {"id": "bad", "description": "", "when": {}, "then": "not_a_verdict"},
        {"id": "ok", "description": "", "when": {"type": "z"}, "then": "approve"},
    ]
    session.get = AsyncMock(return_value=row)
    pid = str(uuid4())
    assert await svc._lookup_rule(session, pid, "nope") is None
    assert await svc._lookup_rule(session, pid, "bad") is None
    found = await svc._lookup_rule(session, pid, "ok")
    assert found is not None
    assert found.id == "ok"


@pytest.mark.asyncio
async def test_lookup_rule_missing_row() -> None:
    svc = PreflightService(PreflightCache(get_redis()))
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    assert await svc._lookup_rule(session, str(uuid4()), "any") is None
    assert await svc._lookup_rule(session, str(uuid4()), None) is None
