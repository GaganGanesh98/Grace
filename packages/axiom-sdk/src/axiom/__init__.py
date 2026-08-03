"""AXIOM Python SDK — governance for AI agents (sync HTTP, minimal dependencies)."""

from __future__ import annotations

from typing import Any

import time

from .client import default_client
from .config import configure, set_debug
from .exceptions import AxiomError, AuthError, GovernanceDenied, GovernanceHeld
from .interceptor import HttpInterceptor
from .models import ChainResult, GovernResult, ReceiptResult, ReportResult, VerifyResult
from .policy_suggester import evaluate_policy, suggest_policy
from .recorder import GovernanceRecorder
from ._version import __version__

__all__ = [
    "init",
    "govern",
    "report",
    "verify",
    "close_chain",
    "get_receipt",
    "wait_for_decision",
    "set_debug",
    "AxiomError",
    "AuthError",
    "GovernanceDenied",
    "GovernanceHeld",
    "GovernResult",
    "ReceiptResult",
    "ReportResult",
    "VerifyResult",
    "ChainResult",
    "__version__",
    "GovernanceRecorder",
    "HttpInterceptor",
    "evaluate_policy",
    "suggest_policy",
]


def init(
    api_key: str,
    base_url: str = "https://api.axiom.dev",
    timeout: float = 30.0,
) -> None:
    """Store API key and config. No HTTP call."""
    configure(api_key=api_key, base_url=base_url, timeout=timeout)


def govern(
    agent_id: str,
    action_type: str,
    target: str,
    risk: str = "low",
    parameters: dict[str, Any] | None = None,
    workflow: str | None = None,
    chain_id: str | None = None,
    enforce: bool = False,
) -> GovernResult:
    """Ask AXIOM for permission before an agent action.

    Returns :class:`GovernResult` with verdict, receipt_id, chain_id.
    If ``enforce=True`` and verdict is ``deny``, raises :class:`GovernanceDenied`.
    If ``enforce=True`` and verdict is ``hold``, raises :class:`GovernanceHeld`.
    """
    return default_client().govern(
        agent_id=agent_id,
        action_type=action_type,
        target=target,
        risk=risk,
        parameters=parameters,
        workflow=workflow,
        chain_id=chain_id,
        enforce=enforce,
    )


def report(receipt_id: str, outcome: dict[str, Any]) -> ReportResult:
    """Report what actually happened after execution.

    Returns :class:`ReportResult` with status, verification result, signatures.
    """
    return default_client().report(receipt_id, outcome)


def verify(receipt_id: str) -> VerifyResult:
    """Verify a governance record's cryptographic integrity.

    POSTs ``{"receipt_id": ...}`` to ``/v1/governance/verify`` for server-side
    verification. Returns :class:`VerifyResult` with ``valid`` and per-algorithm
    ``checks``.
    """
    return default_client().verify(receipt_id)


def close_chain(chain_id: str) -> ChainResult:
    """Close and cryptographically seal a governance chain.

    Returns :class:`ChainResult` with status, counters, and optional chain hash
    when provided by the API.
    """
    return default_client().close_chain(chain_id)


def get_receipt(receipt_id: str) -> ReceiptResult:
    """Fetch the current state of a governance receipt."""
    return default_client().get_receipt(receipt_id)


def wait_for_decision(
    receipt_id: str,
    poll_interval: float = 2.0,
    timeout: float = 1800.0,
) -> ReceiptResult:
    """Poll a held receipt until a final decision is made.

    Returns when ``verdict`` is ``allow`` or ``deny``, or raises :class:`TimeoutError`.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = get_receipt(receipt_id)
        if result.verdict in ("allow", "deny"):
            return result
        time.sleep(poll_interval)
    raise TimeoutError(f"Receipt {receipt_id} still pending after {timeout}s")
