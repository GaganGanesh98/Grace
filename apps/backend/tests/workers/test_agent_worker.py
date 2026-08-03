"""Phase 6.5 — Agent worker orchestration (Batch B). RED until modules exist."""

from __future__ import annotations

import importlib

import pytest


def test_agent_worker_module_and_runner() -> None:
    try:
        mod = importlib.import_module("axiom.workers.agent_worker")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Batch B: add axiom.workers.agent_worker ({exc})")
    assert hasattr(mod, "process_run") or hasattr(mod, "run_agent_job")
