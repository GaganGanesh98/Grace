"""Phase 7.5.1 — Command Center aggregate endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from axiom.config import get_settings
from axiom.db import session_scope
from axiom.models.agent_run import AgentRun, AgentRunStatus
from axiom.models.governance import (
    GovernanceIntent,
    GovernanceReceipt,
    GovernanceVerdict,
)
from axiom.schemas.common import DataEnvelope
from axiom.schemas.command_center import (
    CryptoHealthOut,
    PolicyBreakdownOut,
    PostureOut,
    TsaStatusOut,
)
from tests.api.test_receipts_artifacts_endpoints import _headers_and_project
from tests.fixtures.governance import bootstrap_project_with_api_key

_PREFIX = "/v1/command-center"


def _bearer(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


async def _project_vault_def(client: AsyncClient, h: dict[str, str], pid: str) -> str:
    vk = await client.post(
        "/api/v1/vault",
        headers=h,
        json={"raw_key": "sk-proj-" + "a" * 40, "name": "o"},
    )
    assert vk.status_code == 201, vk.text
    ad = await client.post(
        f"/v1/agent-definitions?project_id={pid}",
        headers=h,
        json={
            "name": "bot",
            "model": "gpt-4o",
            "vault_key_id": vk.json()["id"],
            "system_prompt": "x",
            "tools_config": {},
        },
    )
    assert ad.status_code == 201, ad.text
    return ad.json()["data"]["id"]


def _governance_stub(
    project_id: UUID,
    *,
    verdict: str = "allow",
    execution_data: dict | None = None,
    ed_b: bytes = b"01",
) -> tuple[GovernanceIntent, GovernanceVerdict, GovernanceReceipt]:
    intent = GovernanceIntent(
        id=uuid4(),
        project_id=project_id,
        agent_id="a",
        action_type="t",
        target="https://x",
        risk_declared="low",
    )
    v = GovernanceVerdict(
        id=uuid4(),
        intent_id=intent.id,
        verdict=verdict,
        policy_version="p-v1",
        risk_assessed="low",
    )
    r = GovernanceReceipt(
        id=uuid4(),
        intent_id=intent.id,
        verdict_id=v.id,
        project_id=project_id,
        ed25519_sig=ed_b,
        ml_dsa_sig=ed_b,
        merkle_root=b"root",
        execution_data=execution_data,
        status="sealed",
    )
    return intent, v, r


@pytest.mark.asyncio
async def test_posture_happy_includes_governed_receipts_and_runs(
    client: AsyncClient,
) -> None:
    h, pid = await _headers_and_project(client)
    pid_u = UUID(pid)
    def_id = await _project_vault_def(client, h, pid)
    run = await client.post(
        f"/v1/agent-runs?project_id={pid}",
        headers=h,
        json={"agent_definition_id": def_id, "input": {}},
    )
    assert run.status_code == 201, run.text
    run_id = UUID(run.json()["data"]["id"])
    async with session_scope() as s:
        row = await s.get(AgentRun, run_id)
        assert row
        row.status = AgentRunStatus.SUCCEEDED.value
        row.completed_at = datetime.now(UTC)
        await s.commit()
        i, v, r = _governance_stub(
            pid_u, verdict="deny", ed_b=None
        )  # deny still counts; sigs off for count tests
        i2, v2, r2 = _governance_stub(pid_u, verdict="allow", ed_b=None)
        for a, b, c in ((i, v, r), (i2, v2, r2)):
            s.add(a)
            s.add(b)
            await s.flush()
            s.add(c)
        await s.commit()
    g = await client.get(
        f"{_PREFIX}/posture?window=24h",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    body = g.json()
    assert isinstance(DataEnvelope[PostureOut](data=PostureOut.model_validate(body["data"])).data, PostureOut)
    assert body["data"]["calls_governed"] == 2
    assert body["data"]["runs_completed"] == 1
    assert body["data"]["violations"] == 1


@pytest.mark.asyncio
async def test_posture_empty_project_zeros(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    g = await client.get(
        f"{_PREFIX}/posture?window=24h",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    assert g.json()["data"] == {
        "calls_governed": 0,
        "runs_completed": 0,
        "violations": 0,
    }


@pytest.mark.asyncio
async def test_crypto_health_happy_partial_signing(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    pid_u = UUID(pid)
    ed = b"sig"
    i, v, r1 = _governance_stub(
        pid_u, ed_b=ed, execution_data={}
    )
    i2, v2, r2 = _governance_stub(
        pid_u, ed_b=None, execution_data={}
    )  # second with no signatures
    r2.ed25519_sig = None
    r2.ml_dsa_sig = None
    r2.merkle_root = None
    async with session_scope() as s:
        for a, b, c in ((i, v, r1), (i2, v2, r2)):
            s.add(a)
            s.add(b)
            await s.flush()
            s.add(c)
        await s.commit()
    g = await client.get(
        f"{_PREFIX}/crypto-health",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    CryptoHealthOut.model_validate(d)
    assert d["ed25519_status"] == "partial"
    assert d["mldsa65_status"] == "partial"
    assert d["merkle_status"] == "healthy"
    assert d.get("next_rotation_days") is None  # default unset in test env


@pytest.mark.asyncio
async def test_crypto_health_empty_no_data_signing(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    g = await client.get(
        f"{_PREFIX}/crypto-health",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    assert d["ed25519_status"] == "no_data"
    assert d["mldsa65_status"] == "no_data"
    assert d["merkle_status"] == "no_data"


@pytest.mark.asyncio
async def test_crypto_health_only_pending_receipts_no_data_for_signing(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    pid_u = UUID(pid)
    ed = b"sig"
    i, v, r = _governance_stub(pid_u, ed_b=ed)
    r.status = "pending"
    r.sealed_at = None
    r.ed25519_sig = None
    r.ml_dsa_sig = None
    async with session_scope() as s:
        s.add(i)
        s.add(v)
        await s.flush()
        s.add(r)
        await s.commit()
    g = await client.get(
        f"{_PREFIX}/crypto-health",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    assert d["ed25519_status"] == "no_data"
    assert d["mldsa65_status"] == "no_data"


@pytest.mark.asyncio
async def test_crypto_health_all_sealed_fully_signed(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    pid_u = UUID(pid)
    ed = b"sig"
    i, v, r1 = _governance_stub(pid_u, ed_b=ed)
    i2, v2, r2 = _governance_stub(pid_u, ed_b=ed)
    async with session_scope() as s:
        for a, b, c in ((i, v, r1), (i2, v2, r2)):
            s.add(a)
            s.add(b)
            await s.flush()
            s.add(c)
        await s.commit()
    g = await client.get(
        f"{_PREFIX}/crypto-health",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    CryptoHealthOut.model_validate(d)
    assert d["ed25519_status"] == "all_signed"
    assert d["mldsa65_status"] == "all_signed"


@pytest.mark.asyncio
async def test_policy_breakdown_happy_with_active_policy(
    client: AsyncClient,
) -> None:
    fx = await bootstrap_project_with_api_key(client)
    pid = UUID(fx["project_id"])
    i, v, r = _governance_stub(
        pid, verdict="deny", ed_b=None
    )  # deny + allow via second stub
    i2, v2, r2 = _governance_stub(
        pid, verdict="escalate", ed_b=None
    )
    i3, v3, r3 = _governance_stub(
        pid, verdict="hold", ed_b=None
    )
    i4, v4, r4 = _governance_stub(
        pid, verdict="allow", ed_b=None
    )
    async with session_scope() as s:
        for a, b, c in ((i, v, r), (i2, v2, r2), (i3, v3, r3), (i4, v4, r4)):
            s.add(a)
            s.add(b)
            await s.flush()
            s.add(c)
        await s.commit()
    g = await client.get(
        f"{_PREFIX}/policy-breakdown?window=24h",
        headers=_bearer(fx["api_key_full"]),
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    PolicyBreakdownOut.model_validate(d)
    assert d["policy_name"]
    assert d["evaluated_count"] == 4
    assert d["approved_count"] == 1
    assert d["escalated_count"] == 2
    assert d["denied_count"] == 1


@pytest.mark.asyncio
async def test_policy_breakdown_no_db_policy_is_none_and_zeros(
    client: AsyncClient,
) -> None:
    h, pid = await _headers_and_project(client)
    g = await client.get(
        f"{_PREFIX}/policy-breakdown?window=24h",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    assert d["policy_name"] is None
    assert d["evaluated_count"] == 0
    assert d["approved_count"] == 0
    assert d["escalated_count"] == 0
    assert d["denied_count"] == 0


@pytest.mark.asyncio
async def test_tsa_status_happy_returns_age(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    h, pid = await _headers_and_project(client)
    get_settings.cache_clear()
    try:
        monkeypatch.setenv("AXIOM_TSA_AUTHORITY_URL", "https://example.com/tsa")
    finally:
        get_settings.cache_clear()
    pid_u = UUID(pid)
    tsa = {"token": "dummy-tsa", "timestamp": "2026-01-01T00:00:00Z", "verified": True}
    i, v, r = _governance_stub(pid_u, ed_b=None, execution_data={"tsa": tsa})
    r.created_at = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
    async with session_scope() as s:
        s.add(i)
        s.add(v)
        await s.flush()
        s.add(r)
        await s.commit()
    g = await client.get(
        f"{_PREFIX}/tsa-status",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    TsaStatusOut.model_validate(d)
    assert d["tsa_authority_url"] == "https://example.com/tsa"
    assert d["last_anchor_age_seconds"] is not None
    assert d["last_anchor_age_seconds"] >= 0

    get_settings.cache_clear()
    monkeypatch.delenv("AXIOM_TSA_AUTHORITY_URL", raising=False)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_tsa_status_no_anchor_returns_null_age(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    g = await client.get(
        f"{_PREFIX}/tsa-status",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    d = g.json()["data"]
    assert d["last_anchor_age_seconds"] is None


@pytest.mark.asyncio
async def test_next_rotation_days_84(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    h, pid = await _headers_and_project(client)
    from datetime import datetime as real_dt

    import axiom.services.command_center.aggregates as agg

    class _DT:
        @staticmethod
        def now(tz=None):
            return real_dt(2026, 4, 22, 0, 0, 0, tzinfo=UTC)

    get_settings.cache_clear()
    monkeypatch.setattr(agg, "datetime", type("DT", (), {"now": _DT.now, "UTC": UTC}))
    # date.fromisoformat still on real date
    from datetime import date as dmod

    monkeypatch.setattr(agg, "date", dmod)
    monkeypatch.setenv("AXIOM_KEY_ROTATION_DATE", "2026-07-15")
    get_settings.cache_clear()
    try:
        g = await client.get(
            f"{_PREFIX}/crypto-health",
            headers=h,
            params={"project_id": pid},
        )
        assert g.status_code == 200, g.text
        assert g.json()["data"]["next_rotation_days"] == 84
    finally:
        monkeypatch.delenv("AXIOM_KEY_ROTATION_DATE", raising=False)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_aggregates_require_auth(client: AsyncClient) -> None:
    for path in (
        f"{_PREFIX}/posture?window=24h",
        f"{_PREFIX}/crypto-health",
        f"{_PREFIX}/policy-breakdown?window=24h",
        f"{_PREFIX}/tsa-status",
    ):
        r = await client.get(path)
        assert r.status_code == 401, path


@pytest.mark.asyncio
async def test_data_envelope_mirrors_agent_runs_shape(client: AsyncClient) -> None:
    h, pid = await _headers_and_project(client)
    g = await client.get(
        f"{_PREFIX}/posture?window=24h",
        headers=h,
        params={"project_id": pid},
    )
    assert g.status_code == 200, g.text
    assert set(g.json().keys()) == {"data"}
