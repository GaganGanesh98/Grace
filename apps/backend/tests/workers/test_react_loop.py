"""Phase 6.5 — ReAct / tool loop worker (Batch B). RED until modules exist."""

from __future__ import annotations

import importlib

import pytest


def test_react_loop_module_and_entrypoint() -> None:
    """Batch B: `axiom.workers.react_loop` implements the multi-step LLM loop."""
    try:
        mod = importlib.import_module("axiom.workers.react_loop")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Batch B: add axiom.workers.react_loop ({exc})")
    assert hasattr(mod, "run_react_loop") or hasattr(mod, "run")
