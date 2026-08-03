"""Response dataclasses for the AXIOM Python SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .exceptions import GovernanceDenied


@dataclass
class GovernResult:
    verdict: str  # "allow" | "hold" | "deny"
    receipt_id: str
    chain_id: str | None
    reason: str | None
    policy_version: str | None
    risk_assessed: str | None
    raw: dict[str, Any]

    def require_allow(self) -> None:
        """Raise GovernanceDenied if verdict is not 'allow'."""
        if self.verdict != "allow":
            raise GovernanceDenied(
                verdict=self.verdict,
                reason=self.reason,
                receipt_id=self.receipt_id,
            )


@dataclass
class ReportResult:
    receipt_id: str
    status: str  # "sealed"
    verification: str  # "pass" | "fail" | "unverified"
    signatures: dict[str, Any]
    merkle: dict[str, Any]
    raw: dict[str, Any]


@dataclass
class VerifyResult:
    valid: bool
    checks: dict[str, Any]  # {"ed25519": bool, "ml_dsa_65": bool, "merkle": bool}
    receipt_id: str
    raw: dict[str, Any]


@dataclass
class ReceiptResult:
    receipt_id: str
    verdict: str  # "allow" | "hold" | "deny"
    approval_status: str | None  # "pending" | "approved" | "rejected" | "expired" | None
    approved_by: str | None
    approved_at: str | None
    reason: str | None
    raw: dict[str, Any]


@dataclass
class ChainResult:
    chain_id: str
    status: str
    total_actions: int
    authorized: int
    held: int
    denied: int
    chain_hash: str | None
    raw: dict[str, Any]
