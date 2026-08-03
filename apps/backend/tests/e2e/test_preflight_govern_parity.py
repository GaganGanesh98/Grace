"""Parity: deterministic rules → preflight verdict matches /v1/govern."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fixtures.governance import bootstrap_project_with_api_key


@pytest.mark.asyncio
async def test_preflight_govern_parity_deterministic_rules(client: AsyncClient) -> None:
    rules = []
    for i in range(50):
        rules.append(
            {
                "id": f"r{i}",
                "description": f"rule {i}",
                "when": {"idx": {"op": "eq", "value": i}},
                "then": "approve" if i % 2 == 0 else "deny",
            }
        )
    fx = await bootstrap_project_with_api_key(client, policy_rules=rules)
    auth = {"Authorization": f"Bearer {fx['api_key_full']}"}
    for i in range(50):
        action = {"type": "bench", "idx": i}
        pf = await client.post(
            "/v1/preflight",
            headers=auth,
            json={"action": action, "agent_id": fx["agent_id"], "mode": "enforce"},
        )
        gv = await client.post(
            "/v1/govern",
            headers=auth,
            json={"action": action, "agent_id": fx["agent_id"], "mode": "enforce"},
        )
        assert pf.status_code == 200, pf.text
        assert gv.status_code == 200, gv.text
        assert pf.json()["predicted_verdict"] == gv.json()["verdict"]
