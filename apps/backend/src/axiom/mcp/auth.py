"""API-key authentication for MCP sessions.

Grace deliberately does **not** introduce a separate "passport" credential
type for MCP. The existing ``axm_live_`` / ``axm_test_`` API keys already
carry project scoping, expiry, revocation, and a scope list; a second
credential system would mean a second revocation path, a second storage
surface, and a second thing to get wrong. See ADR-030 in ``docs/decisions.md``.

Two scopes gate the tool surface:

  ``mcp:read``   check_policy, verify_receipt, get_receipt, list_policies
  ``mcp:write``  govern_action

These are deliberately distinct from ``govern:write`` (the scope guarding
``POST /v1/govern``). A key minted for the HTTP API does not silently become
an MCP credential; granting MCP access is an explicit act. For a governance
product, explicit beats convenient.

Session model
-------------
The principal is resolved **once per session** and held in a context
variable, because MCP is a session protocol rather than a request/response
one. Write tools re-verify the key against the database on every call so
that revoking a key takes effect immediately rather than at the end of a
long-lived agent session.
"""

from __future__ import annotations

import os
from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.services.api_key import APIKeyContext
from axiom.services.api_key.service import verify_key

logger = structlog.get_logger(__name__)

SCOPE_READ = "mcp:read"
SCOPE_WRITE = "mcp:write"

#: Environment variable read by the stdio transport.
API_KEY_ENV_VAR = "AXIOM_API_KEY"


class MCPAuthError(Exception):
    """Raised when a session cannot be authenticated or lacks a scope.

    Surfaced to the client as an MCP protocol error. A tool must never
    execute — even partially — without a resolved principal.
    """


@dataclass(frozen=True)
class MCPPrincipal:
    """The authenticated identity behind an MCP session.

    Wraps ``APIKeyContext`` rather than re-deriving identity, and keeps the
    presented secret so that write tools can re-verify revocation state
    mid-session.
    """

    ctx: APIKeyContext
    presented_key: str

    @property
    def project_id(self) -> UUID:
        return self.ctx.project_id

    @property
    def api_key_id(self) -> UUID:
        return self.ctx.api_key_id

    @property
    def scopes(self) -> tuple[str, ...]:
        return self.ctx.scopes

    def require_scope(self, scope: str) -> None:
        if scope not in self.ctx.scopes:
            raise MCPAuthError(
                f"This API key lacks the {scope!r} scope required for this tool. "
                f"Granted scopes: {', '.join(self.ctx.scopes) or '(none)'}."
            )


_principal: ContextVar[MCPPrincipal | None] = ContextVar("axiom_mcp_principal", default=None)


def current_principal() -> MCPPrincipal:
    """Return the principal for the active session, or raise.

    Every tool handler calls this first. There is no unauthenticated path.
    """

    principal = _principal.get()
    if principal is None:
        raise MCPAuthError(
            "No authenticated MCP session. Supply an API key via the "
            f"Authorization header (HTTP transport) or {API_KEY_ENV_VAR} (stdio)."
        )
    return principal


def set_principal(principal: MCPPrincipal | None) -> Token[MCPPrincipal | None]:
    """Bind a principal to the current context. Returns a reset token."""

    return _principal.set(principal)


def reset_principal(token: Token[MCPPrincipal | None]) -> None:
    _principal.reset(token)


def extract_bearer(headers: dict[str, str]) -> str:
    """Pull an API key out of HTTP headers.

    Mirrors ``axiom.deps.require_api_key``: ``Authorization: Bearer <key>``
    first, then ``X-Api-Key``. Header names are matched case-insensitively.
    """

    lowered = {k.lower(): v for k, v in headers.items()}
    auth = lowered.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    return lowered.get("x-api-key", "").strip()


async def resolve_principal(
    db: AsyncSession,
    presented: str,
    *,
    required_scope: str | None = None,
) -> MCPPrincipal:
    """Verify a presented key and build a principal, or raise ``MCPAuthError``.

    Delegates entirely to ``verify_key``, which already narrows by key prefix
    and then compares with ``hmac.compare_digest``. Do not reimplement any
    part of that check here.
    """

    if not presented:
        raise MCPAuthError(
            "API key required. Supply it via the Authorization header "
            f"(HTTP transport) or the {API_KEY_ENV_VAR} environment variable (stdio)."
        )

    ctx = await verify_key(db, presented, required_scope=required_scope)
    if ctx is None:
        # verify_key folds "unknown key", "revoked", "expired", and
        # "missing scope" into a single None. Keep the client-facing message
        # equally undifferentiated so it cannot be used as an oracle.
        raise MCPAuthError("Invalid, expired, revoked, or insufficiently scoped API key.")

    return MCPPrincipal(ctx=ctx, presented_key=presented)


async def reverify_for_write(db: AsyncSession, principal: MCPPrincipal) -> None:
    """Re-check a principal's key before a state-changing tool call.

    A long-lived MCP session must not keep sealing receipts after its key has
    been revoked. This is cheap (one indexed lookup on ``key_prefix``) and it
    is the difference between revocation being immediate and revocation
    being advisory.
    """

    ctx = await verify_key(db, principal.presented_key, required_scope=SCOPE_WRITE)
    if ctx is None:
        logger.warning(
            "mcp.write_after_revocation",
            api_key_id=str(principal.ctx.api_key_id),
            project_id=str(principal.ctx.project_id),
        )
        raise MCPAuthError(
            "API key is no longer valid for writes (revoked, expired, or scope removed). "
            "The action was not governed and no receipt was created."
        )


def api_key_from_env() -> str:
    """Read the stdio transport's API key from the environment."""

    return os.environ.get(API_KEY_ENV_VAR, "").strip()
