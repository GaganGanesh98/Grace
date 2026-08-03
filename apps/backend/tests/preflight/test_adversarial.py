"""Phase 2.25 adversarial gates (Section 8)."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from axiom.db import session_scope
from axiom.models.execution import Execution
from axiom.models.merkle_node import MerkleNode
from axiom.models.policy import Policy
from axiom.models.receipt import Receipt
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.preflight.cache import PreflightCache
from axiom.services.redis_client import get_redis
from tests.conftest import auth_headers
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.asyncio
async def test_adv_preflight_emits_zero_receipts(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "t"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async def counts() -> tuple[int, int, int]:
        async with session_scope() as session:
            e = await session.scalar(select(func.count()).select_from(Execution))
            r = await session.scalar(select(func.count()).select_from(Receipt))
            m = await session.scalar(select(func.count()).select_from(MerkleNode))
        return int(e or 0), int(r or 0), int(m or 0)

    before = await counts()
    for _ in range(100):
        r = await client.post(
            "/v1/preflight",
            headers=_auth(fx["api_key_full"]),
            json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
        )
        assert r.status_code == 200
    assert before == await counts()


@pytest.mark.asyncio
async def test_adv_preflight_govern_parity_deterministic(client: AsyncClient) -> None:
    from tests.e2e import test_preflight_govern_parity as parity_mod

    await parity_mod.test_preflight_govern_parity_deterministic_rules(client)


@pytest.mark.asyncio
async def test_adv_cache_malformed_recovery(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "poison"}, "then": "deny"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    action = {"type": "poison"}
    async with session_scope() as session:
        row = await session.get(Policy, UUID(fx["policy_id"]))
        assert row is not None
        pv = str(row.version)
    h = hashlib.sha256(canonicalize(action)).hexdigest()
    key = PreflightCache._compute_key(
        project_id=fx["project_id"],
        policy_id=fx["policy_id"],
        policy_version=pv,
        agent_id=fx["agent_id"],
        api_key_id=fx["api_key_id"],
        action_canonical_hash_hex=h,
        mode="enforce",
    )
    redis = get_redis()
    await redis.set(key, "{not-json")

    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": action, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    assert r.json()["cached"] is False


@pytest.mark.asyncio
async def test_adv_redis_outage_degrades_gracefully(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "z"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)

    async def boom_get(*_a: object, **_k: object) -> None:
        raise OSError("redis unavailable")

    async def noop_set(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(PreflightCache, "get", boom_get)
    monkeypatch.setattr(PreflightCache, "set", noop_set)

    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "z"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is False
    assert body["predicted_verdict"] == "approve"


@pytest.mark.asyncio
async def test_adv_preflight_reveals_no_more_than_govern(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "cmp"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    action = {"type": "cmp"}
    pf = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": action, "agent_id": fx["agent_id"]},
    )
    gv = await client.post(
        "/v1/govern",
        headers=_auth(fx["api_key_full"]),
        json={"action": action, "agent_id": fx["agent_id"]},
    )
    assert pf.status_code == 200 and gv.status_code == 200
    assert pf.json()["predicted_verdict"] == gv.json()["verdict"]
    assert "receipt_id" not in pf.json()


@pytest.mark.asyncio
async def test_adv_cache_scoped_per_caller(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "scope"}, "then": "approve"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    access = fx["user_access"]
    h = auth_headers(access)
    key2 = await client.post(
        f"/api/v1/projects/{fx['project_id']}/api-keys",
        headers=h,
        json={"name": "k2", "scopes": ["govern:write"]},
    )
    assert key2.status_code == 201, key2.text
    full2 = key2.json()["data"]["full_key"]
    body = {"action": {"type": "scope"}, "agent_id": fx["agent_id"]}
    r1 = await client.post("/v1/preflight", headers=_auth(fx["api_key_full"]), json=body)
    assert r1.status_code == 200
    assert r1.json()["cached"] is False
    r1b = await client.post("/v1/preflight", headers=_auth(fx["api_key_full"]), json=body)
    assert r1b.json()["cached"] is True
    r2 = await client.post("/v1/preflight", headers=_auth(full2), json=body)
    assert r2.status_code == 200
    assert r2.json()["cached"] is False


@pytest.mark.asyncio
async def test_adv_confidence_honest_for_nondeterministic(client: AsyncClient) -> None:
    rules = [
        {
            "id": "age",
            "description": "age",
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
    assert j["confidence"] in {"medium", "low"}


@pytest.mark.asyncio
async def test_adv_response_always_has_disclaimer(client: AsyncClient) -> None:
    rules = [{"id": "a", "description": "d", "when": {"type": "d"}, "then": "deny"}]
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    r = await client.post(
        "/v1/preflight",
        headers=_auth(fx["api_key_full"]),
        json={"action": {"type": "d"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code == 200
    d = r.json()["disclaimer"]
    assert "prediction" in d.lower()
    assert "/v1/govern" in d


def test_adv_no_phase_2_modifications() -> None:
    root = Path(__file__).resolve().parents[4]
    # Crypto is intentionally allowed to drift from v0.2.0-engine (Phase 1.75B baseline: v0.1.75-crypto).
    paths = [
        "apps/backend/src/axiom/services/pipeline/runner.py",
        "apps/backend/src/axiom/services/pipeline/stages/",
        "apps/backend/src/axiom/services/receipt/",
        "apps/backend/src/axiom/routers/govern.py",
        "apps/backend/src/axiom/routers/verify.py",
        "apps/backend/src/axiom/routers/disclose.py",
    ]
    cmd = ["git", "diff", "v0.2.0-engine..HEAD", "--stat", "--", *paths]
    proc = subprocess.run(  # noqa: S603
        cmd, cwd=root, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    assert out == "", f"Phase 2 paths (excluding crypto) must be unchanged vs v0.2.0-engine, got:\n{out}"


def test_adv_no_biological_metaphors() -> None:
    root = Path(__file__).resolve().parents[4]
    needle = "cortex|consciousness|dna|speciation|metabolism|dormancy|osmotic|morphogenetic"
    paths = [
        "apps/backend/src/axiom/services/preflight",
        "apps/backend/src/axiom/services/pipeline/preflight_runner.py",
        "apps/backend/src/axiom/routers/preflight.py",
    ]
    cmd = ["grep", "-riE", needle, *paths]
    proc = subprocess.run(  # noqa: S603
        cmd, cwd=root, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 1, proc.stdout


def test_preflight_rate_limit_is_600_per_minute_in_router() -> None:
    """Contract: /v1/preflight uses the same slowapi pattern as /v1/govern but 600/min.

    Full 601→429 load tests are environment-sensitive (burst timing vs windowing);
    the limit string is the enforced product contract in source.
    """

    path = Path(__file__).resolve().parents[2] / "src" / "axiom" / "routers" / "preflight.py"
    text = path.read_text(encoding="utf-8")
    assert 'limit("600/minute"' in text
    assert "api_key_limit_key" in text
