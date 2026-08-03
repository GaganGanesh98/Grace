"""Tool base class, registry, and governance pre-check."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ToolDenied(Exception):  # noqa: N818
    def __init__(self, receipt_id: str, reason: str) -> None:
        self.receipt_id = receipt_id
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    project_id: UUID
    agent_id: str
    correlation_id: str
    api_base_url: str
    api_key: str
    httpx_client: httpx.AsyncClient
    run_id: UUID | None = None


async def check_governance(
    *,
    ctx: ToolExecutionContext,
    action_type: str,
    target: str,
    parameters: dict[str, object],
    risk: str = "medium",
) -> str:
    """POST /v1/governance/govern. Returns receipt_id. Raises ToolDenied if not allowed."""
    url = f"{ctx.api_base_url.rstrip('/')}/v1/governance/govern"
    body: dict[str, object] = {
        "agent_id": ctx.agent_id,
        "action_type": action_type,
        "target": target,
        "parameters": parameters,
        "risk": risk,
        "mode": "enforce",
        "metadata": {"correlation_id": ctx.correlation_id},
    }
    headers = {"Authorization": f"Bearer {ctx.api_key}"}
    try:
        r = await ctx.httpx_client.post(url, json=body, headers=headers, timeout=60.0)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("governance.request_failed", exc_type=type(exc).__name__)
        msg = "governance_request_failed"
        raise ToolDenied(receipt_id="", reason=msg) from exc

    data = r.json()
    receipt_id = str(data.get("receipt_id", ""))
    verdict = str(data.get("verdict", ""))
    if verdict != "allow":
        reason = str(data.get("reason") or "denied")
        raise ToolDenied(receipt_id=receipt_id, reason=reason)
    return receipt_id


class BaseTool(ABC):
    name: str
    description: str
    schema: dict[str, object]

    @abstractmethod
    async def execute(self, ctx: ToolExecutionContext, **kwargs: object) -> dict[str, object]:
        raise NotImplementedError


class ToolRegistry:
    _instance: ToolRegistry | None = None

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    @classmethod
    def instance(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = ToolRegistry()
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            msg = f"Unknown tool: {name}"
            raise KeyError(msg) from exc

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())


registry = ToolRegistry.instance()
