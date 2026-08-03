"""Phase 6.5 — Run streaming / WebSocket bridge (Batch B). RED until modules exist."""

from __future__ import annotations

import importlib
from uuid import UUID

import pytest

from axiom.services.agent_runs import _ws_token
from axiom.workers.websocket import _validate_token


def test_websocket_module_and_handler() -> None:
    try:
        mod = importlib.import_module("axiom.workers.websocket")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Batch B: add axiom.workers.websocket ({exc})")
    assert hasattr(mod, "handle_run_stream") or hasattr(mod, "stream_handler")


@pytest.mark.asyncio
async def test_websocket_allows_reconnect_with_same_token() -> None:
    """Second WebSocket connection with same valid token must not 403.

    Regression guard for the React 18 Strict Mode double-mount that consumed the
    hash on the first connect and 403'd the second. JWT signature + exp + sub is
    the sole check, so the same token is reusable within its 5-minute expiry.
    """

    run_id = UUID("00000000-0000-0000-0000-000000000099")
    token = _ws_token(run_id)

    assert await _validate_token(run_id, token) is True
    assert await _validate_token(run_id, token) is True


@pytest.mark.asyncio
async def test_websocket_rejects_token_for_other_run() -> None:
    """Token minted for run A must not validate for run B."""

    run_a = UUID("00000000-0000-0000-0000-0000000000aa")
    run_b = UUID("00000000-0000-0000-0000-0000000000bb")
    token = _ws_token(run_a)

    assert await _validate_token(run_b, token) is False


@pytest.mark.asyncio
async def test_websocket_rejects_missing_or_garbage_token() -> None:
    run_id = UUID("00000000-0000-0000-0000-0000000000cc")
    assert await _validate_token(run_id, None) is False
    assert await _validate_token(run_id, "not-a-jwt") is False
