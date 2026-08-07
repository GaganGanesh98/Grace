"""FastMCP server construction and tool registration.

Kept thin on purpose. Each registered function does three things: resolve the
session principal, open a DB session, delegate to ``axiom.mcp.tools``. Any
logic beyond that belongs a layer down.

Tool descriptions are written for a language model, not for a developer
skimming an API reference — they state obligations ("you must not proceed")
rather than merely describing return shapes, because the description is
frequently all the model reads before deciding whether to call the tool.
"""

from __future__ import annotations

from typing import Any

import structlog
from mcp.server.mcpserver import MCPServer

from axiom.db import session_scope
from axiom.mcp import schemas, tools
from axiom.mcp.auth import MCPAuthError, current_principal
from axiom.mcp.tools import ToolError

logger = structlog.get_logger(__name__)

SERVER_NAME = "grace-governance"
SERVER_INSTRUCTIONS = """\
Grace is a governance layer for AI agents. It decides whether an action is \
permitted, and produces a cryptographically signed, independently verifiable \
receipt for every decision.

Use `govern_action` BEFORE performing any consequential action. It returns a \
verdict you are obliged to honour:

  * ALLOWED  — proceed as submitted
  * DENIED   — do not perform the action, and do not attempt a variation
               designed to get a different answer
  * MODIFIED — discard your action and use the supplied modification instead
  * ESCALATED— stop and report that human approval is pending

Use `check_policy` to test a prospective action cheaply. It creates no receipt \
and is not an audit record.

Every `govern_action` call produces a receipt that anyone can verify at the \
returned verify_url without an account.
"""


def build_server() -> MCPServer:
    """Construct the MCP server with all five tools registered.

    Targets the MCP Python SDK 2.x API (``MCPServer``). The 1.x name for this
    class was ``FastMCP`` at ``mcp.server.fastmcp``; the SDK renamed it in 2.0,
    which is why ``pyproject.toml`` pins ``mcp>=2.0``.
    """

    mcp = MCPServer(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

    @mcp.tool(
        name="govern_action",
        description=(
            "Submit an action for governance BEFORE performing it. Returns a verdict "
            "(approve / deny / modify / escalate) that you must honour, plus a signed, "
            "publicly verifiable receipt. Read the 'decision' field first: it states in "
            "plain language whether you may proceed. If the verdict is deny or escalate "
            "you must not perform the action. If it is modify, you must use the returned "
            "'modification' in place of your original action. Requires the 'mcp:write' scope."
        ),
    )
    async def govern_action_tool(
        action: dict[str, Any],
        agent_id: str,
        mode: str = "enforce",
    ) -> dict[str, Any]:
        payload = schemas.GovernActionInput.model_validate(
            {"action": action, "agent_id": agent_id, "mode": mode}
        )
        principal = current_principal()
        async with session_scope() as db:
            result = await tools.govern_action(db, principal, payload)
        return result.model_dump(mode="json")

    @mcp.tool(
        name="check_policy",
        description=(
            "Dry-run a policy evaluation for a prospective action. Tells you what verdict "
            "govern_action would return, without governing anything. IMPORTANT: this "
            "creates NO receipt and is NOT an audit record — it cannot be used as evidence "
            "that an action was authorised. Call govern_action for anything you intend to "
            "actually do. Requires the 'mcp:read' scope."
        ),
    )
    async def check_policy_tool(
        action: dict[str, Any],
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        payload = schemas.CheckPolicyInput.model_validate(
            {"action": action, "policy_id": policy_id}
        )
        principal = current_principal()
        async with session_scope() as db:
            result = await tools.check_policy(db, principal, payload)
        return result.model_dump(mode="json")

    @mcp.tool(
        name="verify_receipt",
        description=(
            "Verify that a receipt is authentic and provably part of the audit log. Runs "
            "four independent checks: Ed25519 signature, ML-DSA-65 (post-quantum) "
            "signature, RFC 6962 Merkle inclusion proof, and payload hash. All four must "
            "pass for 'verified' to be true. Requires the 'mcp:read' scope."
        ),
    )
    async def verify_receipt_tool(receipt_id: str) -> dict[str, Any]:
        payload = schemas.VerifyReceiptInput(receipt_id=receipt_id)
        principal = current_principal()
        async with session_scope() as db:
            result = await tools.verify_receipt(db, principal, payload)
        return result.model_dump(mode="json")

    @mcp.tool(
        name="get_receipt",
        description=(
            "Fetch the metadata for a single receipt in your project — verdict, "
            "signing algorithm, Merkle position, and a public verification URL. Does not "
            "return encrypted evidence. Requires the 'mcp:read' scope."
        ),
    )
    async def get_receipt_tool(receipt_id: str) -> dict[str, Any]:
        payload = schemas.GetReceiptInput(receipt_id=receipt_id)
        principal = current_principal()
        async with session_scope() as db:
            result = await tools.get_receipt(db, principal, payload)
        return result.model_dump(mode="json")

    @mcp.tool(
        name="list_policies",
        description=(
            "List the governance policies that apply to your project, including their "
            "rules. Read these to understand what is permitted before acting, rather than "
            "discovering the boundaries through denials. Rules are evaluated in order and "
            "the first match wins; if nothing matches, the action is denied. Requires the "
            "'mcp:read' scope."
        ),
    )
    async def list_policies_tool(*, include_inactive: bool = False) -> dict[str, Any]:
        payload = schemas.ListPoliciesInput(include_inactive=include_inactive)
        principal = current_principal()
        async with session_scope() as db:
            result = await tools.list_policies(db, principal, payload)
        return result.model_dump(mode="json")

    # Bind the registered callables so linters do not flag them as unused;
    # FastMCP holds its own references via the decorator.
    _ = (
        govern_action_tool,
        check_policy_tool,
        verify_receipt_tool,
        get_receipt_tool,
        list_policies_tool,
    )
    return mcp


__all__ = ["SERVER_NAME", "MCPAuthError", "MCPServer", "ToolError", "build_server"]
