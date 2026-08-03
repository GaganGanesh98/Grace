"""Phase 7.2 — ReAct loop collects gateway receipt IDs and tool artifacts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from axiom.workers.react_loop import run_react_loop


def _run_stub(
    *,
    correlation_id: str = "cid",
    input_payload: dict | None = None,
) -> SimpleNamespace:
    rid = uuid4()
    return SimpleNamespace(
        id=rid,
        project_id=uuid4(),
        correlation_id=correlation_id,
        input_payload=input_payload or {},
    )


def _def_stub(*, agent_id: UUID | None = None, max_iterations: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        agent_id=agent_id or uuid4(),
        system_prompt=None,
        model="llama-3",
        max_iterations=max_iterations,
        max_tokens_per_run=100_000,
    )


def _vault_stub(service: str = "groq") -> SimpleNamespace:
    return SimpleNamespace(service=service)


def _openai_msg(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
    }


@pytest.mark.asyncio
async def test_react_loop_collects_receipt_ids_across_iterations() -> None:
    """Two LLM rounds each expose X-Axiom-Receipt-Id; both IDs appear in outcome."""
    run = _run_stub()
    definition = _def_stub(max_iterations=10)
    vault = _vault_stub()
    calls = {"n": 0}
    rids = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]

    async def fake_post(**_kwargs: object) -> tuple[dict, str | None]:
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                _openai_msg(
                    'Thought: t\nAction: file_write\nAction Input: {"filename":"x.txt","content":""}',
                ),
                rids[0],
            )
        return _openai_msg("Final Answer: ok"), rids[1]

    async def fake_dispatch(_name: str, _ctx: object, **_kw: object) -> dict:
        return {"ok": True, "echo": 1}

    with (
        patch("axiom.workers.react_loop._post_gateway_completion", side_effect=fake_post),
        patch("axiom.workers.react_loop.dispatch_tool", side_effect=fake_dispatch),
    ):
        httpx_client = AsyncMock()
        out = await run_react_loop(
            run=run,
            definition=definition,
            vault_key=vault,
            httpx_client=httpx_client,
            gateway_api_key="k",
            event_sink=None,
        )
    assert out["ok"] is True
    assert out.get("receipt_ids") == rids
    assert out.get("total_tokens") == 10


@pytest.mark.asyncio
async def test_react_loop_collects_artifacts_from_file_write() -> None:
    """file_write-shaped tool results become collected_artifacts entries."""
    run = _run_stub()
    definition = _def_stub(max_iterations=10)
    vault = _vault_stub()
    rid_llm = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    calls = {"n": 0}

    async def fake_post(**_kwargs: object) -> tuple[dict, str | None]:
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                _openai_msg(
                    'Thought: w\nAction: file_write\nAction Input: {"filename":"pi.txt","content":"314"}',
                ),
                rid_llm,
            )
        return _openai_msg("Final Answer: wrote pi"), rid_llm

    async def fake_dispatch(_name: str, _ctx: object, **kwargs: object) -> dict:
        assert _name == "file_write"
        return {
            "ok": True,
            "url": f"/artifacts/{run.id}/pi.txt",
            "content_type": "text/plain",
            "size_bytes": 3,
        }

    with (
        patch("axiom.workers.react_loop._post_gateway_completion", side_effect=fake_post),
        patch("axiom.workers.react_loop.dispatch_tool", side_effect=fake_dispatch),
    ):
        httpx_client = AsyncMock()
        out = await run_react_loop(
            run=run,
            definition=definition,
            vault_key=vault,
            httpx_client=httpx_client,
            gateway_api_key="k",
            event_sink=None,
        )

    arts = out.get("artifacts")
    assert isinstance(arts, list) and len(arts) == 1
    a0 = arts[0]
    assert a0["tool"] == "file_write"
    assert a0["path"] == "pi.txt"
    assert a0["url"].startswith("/api/")
    assert a0["content_type"] == "text/plain"
    assert a0["size_bytes"] == 3
    assert "created_at" in a0


@pytest.mark.asyncio
async def test_react_loop_returns_both_lists_on_exhaustion() -> None:
    """Max iterations reached: outcome includes accumulated receipt_ids and artifacts."""
    run = _run_stub()
    definition = _def_stub(max_iterations=2)
    vault = _vault_stub()
    seq = [
        (
            _openai_msg('Action: file_write\nAction Input: {"filename":"a.txt","content":"x"}'),
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        ),
        (
            _openai_msg('Action: file_write\nAction Input: {"filename":"b.txt","content":"y"}'),
            "cccccccc-cccc-cccc-cccc-cccccccccccc",
        ),
    ]

    async def fake_post(**_kwargs: object) -> tuple[dict, str | None]:
        return seq.pop(0)

    async def fake_dispatch(_name: str, _ctx: object, **_kw: object) -> dict:
        return {
            "ok": True,
            "url": f"/artifacts/{run.id}/x",
            "content_type": "application/octet-stream",
            "size_bytes": 1,
        }

    with (
        patch("axiom.workers.react_loop._post_gateway_completion", side_effect=fake_post),
        patch("axiom.workers.react_loop.dispatch_tool", side_effect=fake_dispatch),
    ):
        httpx_client = AsyncMock()
        out = await run_react_loop(
            run=run,
            definition=definition,
            vault_key=vault,
            httpx_client=httpx_client,
            gateway_api_key="k",
            event_sink=None,
        )
    assert out.get("truncated") is True
    assert out.get("truncation_reason") == "max_iterations"
    assert len(out.get("receipt_ids", [])) == 2
    assert len(out.get("artifacts", [])) == 2


@pytest.mark.asyncio
async def test_react_loop_returns_both_lists_on_failure() -> None:
    """LLM step failure still returns lists (possibly empty partials)."""
    run = _run_stub()
    definition = _def_stub()
    vault = _vault_stub()

    async def fake_post(**_kwargs: object) -> tuple[dict, str | None]:
        raise RuntimeError("network")

    with patch("axiom.workers.react_loop._post_gateway_completion", side_effect=fake_post):
        httpx_client = AsyncMock()
        out = await run_react_loop(
            run=run,
            definition=definition,
            vault_key=vault,
            httpx_client=httpx_client,
            gateway_api_key="k",
            event_sink=None,
        )
    assert out["ok"] is False
    assert out.get("receipt_ids") == []
    assert out.get("artifacts") == []
