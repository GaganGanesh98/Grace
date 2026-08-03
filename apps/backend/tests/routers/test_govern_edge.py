"""Edge-case coverage for /v1/govern."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from axiom.services.pipeline.protocols import PipelineContext, PipelineMode
from tests.fixtures.governance import bootstrap_project_with_api_key


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.asyncio
async def test_govern_rejects_invalid_content_length(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client)
    r = await client.post(
        "/v1/govern",
        headers={
            **_auth(fx["api_key_full"]),
            "content-length": "not-a-number",
        },
        json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_govern_500_when_receipt_generation_fails(client: AsyncClient) -> None:
    """Simulate ReceiptService returning an incomplete context (evidence/receipt failure)."""

    fx = await bootstrap_project_with_api_key(client)
    from datetime import UTC, datetime

    broken_ctx = PipelineContext(
        project_id=fx["project_id"],  # type: ignore[arg-type]
        agent_id=fx["agent_id"],  # type: ignore[arg-type]
        api_key_id=fx["api_key_id"],  # type: ignore[arg-type]
        correlation_id="corr",
        action={"type": "t"},
        mode=PipelineMode.ENFORCE,
        requested_at=datetime.now(UTC),
    )
    # receipt_id / decision / signature all None => triggers 500

    async def _stub_process(self, **_kwargs):
        return broken_ctx

    with patch(
        "axiom.routers.govern.ReceiptService.process",
        new=_stub_process,
    ):
        r = await client.post(
            "/v1/govern",
            headers=_auth(fx["api_key_full"]),
            json={"action": {"type": "t"}, "agent_id": fx["agent_id"]},
        )
    assert r.status_code == 500
    assert "Receipt generation failed" in r.json().get("detail", "")
