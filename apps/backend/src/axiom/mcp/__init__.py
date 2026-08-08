"""MCP governance server (Phase 7.0).

Exposes Grace's governance surface as Model Context Protocol tools so that
agents can consult the policy engine and seal receipts through the protocol
they already speak, rather than requiring a bespoke HTTP integration.

This package is a **transport and tool surface only**. Every governance
primitive it exposes already exists:

  * ``axiom.services.policy.evaluator``  — verdicts
  * ``axiom.services.crypto``            — Ed25519 + ML-DSA-65 hybrid signing
  * ``axiom.services.receipt``           — RFC 6962 Merkle receipts
  * ``axiom.services.pipeline``          — the six-stage runner

Nothing in here may reimplement policy, signing, or Merkle logic. A governed
action reached over MCP must traverse the *identical* audited path as one
reached over ``POST /v1/govern`` so that the receipt chain has no
second-class entries.

Layering: ``axiom.mcp`` sits at the router layer. It may import
``axiom.services``; it must never be imported by ``axiom.services``,
``axiom.models``, or ``axiom.core``. See ``.importlinter`` contract 5.
"""

from __future__ import annotations

from axiom.mcp.auth import (
    SCOPE_READ,
    SCOPE_WRITE,
    MCPAuthError,
    MCPPrincipal,
    current_principal,
)

__all__ = [
    "SCOPE_READ",
    "SCOPE_WRITE",
    "MCPAuthError",
    "MCPPrincipal",
    "current_principal",
]
