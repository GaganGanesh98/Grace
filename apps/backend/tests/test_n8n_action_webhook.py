"""Reusable governed-action webhook: HMAC, idempotency, verdict shapes (Phase 9.1)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from axiom.config import get_settings
from axiom.db import session_scope
from axiom.models.governance import GovernanceIntent, GovernanceReceipt
from axiom.models.project import Project
from axiom.services.escalation.signing import SIGNATURE_HEADER, sign_body
from axiom.services.governance.idempotency import run_key
from axiom.services.redis_client import get_redis
from tests.fixtures.governance import bootstrap_project_with_api_key

ENDPOINT = "/webhooks/n8n/govern-action"
SECRET = "test_action_secret"


@pytest.fixture
def action_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("N8N_ACTION_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _signed(body: dict[str, Any], *, secret: str = SECRET) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode("utf-8")
    return raw, {SIGNATURE_HEADER: sign_body(secret, raw), "Content-Type": "application/json"}


def _action(project_id: str, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "workflow_id": "wf-invoices",
        "workflow_run_id": f"run-{uuid4().hex[:12]}",
        "project_id": project_id,
        "agent_id": "n8n-finance",
        "action_type": "payment.send",
        "target": "https://api.stripe.com/v1/transfers",
        "parameters": {"amount": 100},
        "risk": "low",
    }
    body.update(over)
    return body


async def _project_with_policy(client: AsyncClient) -> str:
    """A project on starter-safe, so an unmatched high-risk action holds."""
    fx = await bootstrap_project_with_api_key(client, policy_rules=[])
    async with session_scope() as session:
        project = await session.get(Project, UUID(fx["project_id"]))
        assert project is not None
        settings = dict(project.settings)
        settings["governance_policy"] = "starter-safe"
        project.settings = settings
    return str(fx["project_id"])


async def _receipt_count(project_id: str) -> int:
    async with session_scope() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(GovernanceReceipt)
                .where(GovernanceReceipt.project_id == UUID(project_id))
            )
            or 0
        )


@pytest.mark.usefixtures("action_secret")
async def test_valid_signature_returns_a_verdict_and_receipt(client: AsyncClient) -> None:
    project_id = await _project_with_policy(client)
    raw, headers = _signed(_action(project_id))

    resp = await client.post(ENDPOINT, content=raw, headers=headers)

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["verdict"] in {"allow", "deny", "hold"}
    assert UUID(payload["receipt_id"])
    assert payload["verify_url"].endswith(f"/v1/verify/{payload['receipt_id']}")
    assert payload["replayed"] is False
    assert payload["corrected_parameters"] is None


@pytest.mark.usefixtures("action_secret")
async def test_tampered_body_is_401_and_creates_no_receipt(client: AsyncClient) -> None:
    project_id = await _project_with_policy(client)
    before = await _receipt_count(project_id)
    raw, headers = _signed(_action(project_id))

    resp = await client.post(ENDPOINT, content=raw + b" ", headers=headers)

    assert resp.status_code == 401
    assert await _receipt_count(project_id) == before


@pytest.mark.usefixtures("action_secret")
async def test_missing_signature_is_401(client: AsyncClient) -> None:
    project_id = await _project_with_policy(client)
    raw = json.dumps(_action(project_id)).encode("utf-8")

    resp = await client.post(ENDPOINT, content=raw, headers={"Content-Type": "application/json"})

    assert resp.status_code == 401


@pytest.mark.usefixtures("action_secret")
async def test_escalation_secret_is_not_accepted(client: AsyncClient) -> None:
    """Different trust boundary, different key — no cross-acceptance."""
    project_id = await _project_with_policy(client)
    raw, headers = _signed(_action(project_id), secret="test_callback_secret")

    resp = await client.post(ENDPOINT, content=raw, headers=headers)

    assert resp.status_code == 401


async def test_missing_secret_is_503(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("N8N_ACTION_SECRET", raising=False)
    monkeypatch.delenv("GRACE_N8N_ACTION_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        raw = json.dumps(_action(str(uuid4()))).encode("utf-8")
        resp = await client.post(
            ENDPOINT, content=raw, headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 503
    finally:
        get_settings.cache_clear()


@pytest.mark.usefixtures("action_secret")
async def test_replayed_run_id_returns_the_same_receipt_and_governs_once(
    client: AsyncClient,
) -> None:
    """An n8n retry must not create a second receipt for one real action."""
    project_id = await _project_with_policy(client)
    body = _action(project_id)
    raw, headers = _signed(body)
    before = await _receipt_count(project_id)

    first = await client.post(ENDPOINT, content=raw, headers=headers)
    assert first.status_code == 200, first.text
    second = await client.post(ENDPOINT, content=raw, headers=headers)
    assert second.status_code == 200, second.text

    assert first.json()["receipt_id"] == second.json()["receipt_id"]
    assert first.json()["verdict"] == second.json()["verdict"]
    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True
    assert await _receipt_count(project_id) == before + 1


@pytest.mark.usefixtures("action_secret")
async def test_distinct_run_ids_each_get_a_receipt(client: AsyncClient) -> None:
    project_id = await _project_with_policy(client)
    before = await _receipt_count(project_id)

    ids = set()
    for _ in range(2):
        raw, headers = _signed(_action(project_id))
        resp = await client.post(ENDPOINT, content=raw, headers=headers)
        assert resp.status_code == 200, resp.text
        ids.add(resp.json()["receipt_id"])

    assert len(ids) == 2
    assert await _receipt_count(project_id) == before + 2


@pytest.mark.usefixtures("action_secret")
async def test_successful_run_records_the_receipt_against_the_claim(client: AsyncClient) -> None:
    project_id = await _project_with_policy(client)
    body = _action(project_id)
    raw, headers = _signed(body)

    resp = await client.post(ENDPOINT, content=raw, headers=headers)
    assert resp.status_code == 200, resp.text

    # The claim holds the receipt, not the in-flight sentinel.
    stored = await get_redis().get(run_key(body["workflow_id"], body["workflow_run_id"]))
    assert stored == resp.json()["receipt_id"]


@pytest.mark.usefixtures("action_secret")
async def test_claim_is_released_when_governance_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed run must not stay claimed, or a retry is stranded for the whole TTL."""
    project_id = await _project_with_policy(client)
    body = _action(project_id)
    raw, headers = _signed(body)

    async def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("policy engine exploded")

    monkeypatch.setattr("axiom.routers.webhooks.execute_governed_action", _boom)

    resp = await client.post(ENDPOINT, content=raw, headers=headers)
    assert resp.status_code == 500

    assert await get_redis().get(run_key(body["workflow_id"], body["workflow_run_id"])) is None


@pytest.mark.usefixtures("action_secret")
async def test_hold_verdict_reports_hold(client: AsyncClient) -> None:
    project_id = await _project_with_policy(client)
    raw, headers = _signed(_action(project_id, risk="high", action_type="t", target="https://x"))

    resp = await client.post(ENDPOINT, content=raw, headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["verdict"] == "hold"
    assert resp.json()["reason"]


@pytest.mark.usefixtures("action_secret")
async def test_advise_mode_answers_allow_but_records_the_real_verdict(
    client: AsyncClient,
) -> None:
    """`advise` is shadow mode: the workflow proceeds, the receipt tells the truth."""
    project_id = await _project_with_policy(client)
    raw, headers = _signed(
        _action(project_id, risk="high", action_type="t", target="https://x", mode="advise")
    )

    resp = await client.post(ENDPOINT, content=raw, headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["verdict"] == "allow"

    async with session_scope() as session:
        receipt = await session.get(GovernanceReceipt, UUID(resp.json()["receipt_id"]))
        assert receipt is not None
        intent = await session.get(GovernanceIntent, receipt.intent_id)
        assert intent is not None
        assert intent.mode == "shadow"


@pytest.mark.usefixtures("action_secret")
async def test_workflow_provenance_is_recorded_on_the_intent(client: AsyncClient) -> None:
    """'Which workflow did this?' has to be answerable from the audit chain."""
    project_id = await _project_with_policy(client)
    body = _action(project_id)
    raw, headers = _signed(body)

    resp = await client.post(ENDPOINT, content=raw, headers=headers)
    assert resp.status_code == 200, resp.text

    async with session_scope() as session:
        receipt = await session.get(GovernanceReceipt, UUID(resp.json()["receipt_id"]))
        assert receipt is not None
        intent = await session.get(GovernanceIntent, receipt.intent_id)
        assert intent is not None
        assert intent.extra_metadata["source"] == "n8n"
        assert intent.extra_metadata["workflow_id"] == body["workflow_id"]
        assert intent.extra_metadata["workflow_run_id"] == body["workflow_run_id"]


@pytest.mark.usefixtures("action_secret")
async def test_invalid_body_is_422(client: AsyncClient) -> None:
    raw, headers = _signed({"workflow_id": "wf", "not_a_field": True})

    resp = await client.post(ENDPOINT, content=raw, headers=headers)

    assert resp.status_code == 422


@pytest.mark.usefixtures("action_secret")
async def test_concurrent_duplicate_is_409(client: AsyncClient) -> None:
    """A second call while the first is mid-flight must not mint a second receipt."""
    project_id = await _project_with_policy(client)
    body = _action(project_id)
    raw, headers = _signed(body)

    await get_redis().set(run_key(body["workflow_id"], body["workflow_run_id"]), "__in_flight__")
    try:
        resp = await client.post(ENDPOINT, content=raw, headers=headers)
        assert resp.status_code == 409
    finally:
        await get_redis().delete(run_key(body["workflow_id"], body["workflow_run_id"]))
