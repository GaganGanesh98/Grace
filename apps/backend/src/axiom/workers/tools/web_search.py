"""Tavily-backed web search (optional when API key is configured)."""

from __future__ import annotations

from typing import Any, ClassVar

from axiom.config import get_settings
from axiom.workers.tools.base import BaseTool, ToolExecutionContext, check_governance


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the public web via Tavily (requires Tavily API key)."
    schema: ClassVar[dict[str, object]] = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }

    async def execute(self, ctx: ToolExecutionContext, **kwargs: object) -> dict[str, object]:
        query = str(kwargs.get("query", "")).strip()
        await check_governance(
            ctx=ctx,
            action_type="tool.web_search",
            target=query[:1024],
            parameters={"query": query},
        )
        settings = get_settings()
        key = settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else None
        if not key:
            return {"ok": False, "disabled": True, "results": []}

        body: dict[str, Any] = {
            "api_key": key,
            "query": query,
            "search_depth": "basic",
        }
        r = await ctx.httpx_client.post(
            "https://api.tavily.com/search",
            json=body,
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
        raw_results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(raw_results, list):
            return {"ok": True, "results": []}
        out: list[dict[str, str]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", ""))
            url = str(item.get("url", ""))
            snippet = str(item.get("content", item.get("snippet", "")))
            out.append({"title": title, "url": url, "snippet": snippet})
        return {"ok": True, "results": out}
