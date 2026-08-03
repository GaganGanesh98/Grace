"""Registered tools and dispatch."""

from __future__ import annotations

from typing import Any

from axiom.workers.tools.base import BaseTool, ToolExecutionContext, ToolRegistry, registry
from axiom.workers.tools.file_write import FileWriteTool
from axiom.workers.tools.http_fetch import HttpFetchTool
from axiom.workers.tools.web_search import WebSearchTool

_TOOLS_SEEDED = False


def _ensure_registered() -> None:
    global _TOOLS_SEEDED
    if _TOOLS_SEEDED:
        return
    registry.register(HttpFetchTool())
    registry.register(WebSearchTool())
    registry.register(FileWriteTool())
    _TOOLS_SEEDED = True


_ensure_registered()


async def dispatch_tool(name: str, ctx: ToolExecutionContext, **kwargs: Any) -> dict[str, object]:
    """Execute a tool by name with governance + tool-local checks."""
    _ensure_registered()
    tool = registry.get(name)
    return await tool.execute(ctx, **kwargs)


__all__ = [
    "BaseTool",
    "FileWriteTool",
    "HttpFetchTool",
    "ToolExecutionContext",
    "ToolRegistry",
    "WebSearchTool",
    "dispatch_tool",
    "registry",
]
