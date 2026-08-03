"""ReAct loop: gateway LLM completions + tools; plain-text ReAct for Llama on Groq."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import structlog

from axiom.config import get_settings
from axiom.models.agent_definition import AgentDefinition
from axiom.models.agent_run import AgentRun
from axiom.models.vault import VaultKey
from axiom.workers.gateway_routes import gateway_llm_url
from axiom.workers.tools import dispatch_tool, registry
from axiom.workers.tools.base import ToolDenied, ToolExecutionContext

logger = structlog.get_logger(__name__)

_REACT_FORMAT = """\
You have access to the following tools:
{tool_list}

To use a tool, respond ONLY in this exact format (one tool per response):
Thought: <your reasoning>
Action: <tool_name>
Action Input: <valid JSON object with the tool arguments>

When you have a final answer and no longer need tools, respond ONLY in this format:
Final Answer: <your complete answer>

Do not output any text outside these two formats."""


def _build_react_system_prompt(base_prompt: str | None) -> str:
    tool_lines = [f"- {t.name}: {t.description}" for t in registry.list_tools()]
    tool_list = "\n".join(tool_lines) if tool_lines else "(none)"
    react_header = _REACT_FORMAT.format(tool_list=tool_list)
    if base_prompt:
        return f"{react_header}\n\n{base_prompt}"
    return react_header


def _openai_messages_from_history(
    system_prompt: str | None,
    user_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    messages.append({"role": "system", "content": _build_react_system_prompt(system_prompt)})
    user_text = json.dumps(user_payload or {}, separators=(",", ":"))
    messages.append({"role": "user", "content": user_text})
    return messages


async def _post_gateway_completion(
    *,
    httpx_client: httpx.AsyncClient,
    gateway_api_key: str,
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
    x_axiom_agent_id: str,
) -> tuple[dict[str, Any], str | None]:
    settings = get_settings()
    url = gateway_llm_url(provider)
    body: dict[str, Any] = {"model": model, "messages": messages}
    headers = {
        "Authorization": f"Bearer {gateway_api_key}",
        "Content-Type": "application/json",
        "X-Axiom-Agent-Id": x_axiom_agent_id,
    }
    timeout = float(settings.gateway_request_timeout_seconds)
    response = await httpx_client.post(url, json=body, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        msg = "gateway_invalid_json_object"
        raise RuntimeError(msg)
    raw_rid = response.headers.get("X-Axiom-Receipt-Id")
    receipt_id = str(raw_rid).strip() if raw_rid else None
    return data, receipt_id


def _extract_text_from_response(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        return str(content) if isinstance(content, str) else ""
    return str(first.get("text", ""))


_ACTION_RE = re.compile(r"Action\s*:\s*(.+)", re.IGNORECASE)
_ACTION_INPUT_RE = re.compile(r"Action Input\s*:\s*(\{.*\})", re.IGNORECASE | re.DOTALL)
_FINAL_ANSWER_RE = re.compile(r"Final Answer\s*:\s*(.+)", re.IGNORECASE | re.DOTALL)


def _parse_react_response(text: str) -> dict[str, Any]:
    """Extract action or final-answer from plain-text ReAct output."""
    fa = _FINAL_ANSWER_RE.search(text)
    if fa:
        return {"type": "final_answer", "text": fa.group(1).strip()}
    am = _ACTION_RE.search(text)
    if am:
        action_name = am.group(1).strip()
        args: dict[str, Any] = {}
        aim = _ACTION_INPUT_RE.search(text)
        if aim:
            try:
                args = json.loads(aim.group(1).strip())
            except json.JSONDecodeError:
                args = {}
        return {"type": "action", "name": action_name, "args": args}
    # No recognized pattern — treat full text as final answer
    return {"type": "final_answer", "text": text.strip()}


def _artifact_entry_for_file_write(
    *,
    project_id: UUID,
    run_id: UUID,
    args: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any] | None:
    fn = str(args.get("filename", "")).strip()
    if not fn:
        return None
    ct = result.get("content_type")
    sz = result.get("size_bytes")
    url = f"/api/projects/{project_id}/agent-runs/{run_id}/artifacts/{fn}"
    return {
        "tool": "file_write",
        "path": fn,
        "url": url,
        "content_type": str(ct) if ct is not None else "application/octet-stream",
        "size_bytes": int(sz) if isinstance(sz, int) else 0,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _usage_tokens_from_response(data: dict[str, Any], provider: str) -> int:
    """Best-effort token count from provider ``usage`` (OpenAI-compatible or Anthropic)."""
    u = data.get("usage")
    if not isinstance(u, dict):
        return 0
    p = provider.lower()
    if p == "anthropic":
        inp = u.get("input_tokens")
        out = u.get("output_tokens")
        ni = int(inp) if isinstance(inp, int) else 0
        no = int(out) if isinstance(out, int) else 0
        return max(0, ni + no)
    tt = u.get("total_tokens")
    if isinstance(tt, int):
        return max(0, tt)
    pt = u.get("prompt_tokens")
    ct = u.get("completion_tokens")
    if isinstance(pt, int) and isinstance(ct, int):
        return max(0, pt + ct)
    return 0


async def run_react_loop(
    *,
    run: AgentRun,
    definition: AgentDefinition,
    vault_key: VaultKey,
    httpx_client: httpx.AsyncClient,
    gateway_api_key: str,
    event_sink: Any | None = None,
) -> dict[str, Any]:
    """Run up to ``max_iterations`` rounds; tool denials stay in the message list."""

    provider = vault_key.service
    user_pl: dict[str, Any] = run.input_payload if isinstance(run.input_payload, dict) else {}
    if user_pl.get("dry_run") is True:
        return {
            "ok": True,
            "final_text": "[dry run] Goal recorded; no LLM execution.",
            "iterations": 0,
            "total_tokens": 0,
            "receipt_ids": [],
            "artifacts": [],
            "dry_run": True,
        }
    messages = _openai_messages_from_history(definition.system_prompt, user_pl)
    raw_max = user_pl.get("max_iter")
    if isinstance(raw_max, int) or (isinstance(raw_max, str) and str(raw_max).isdigit()):
        mi = int(raw_max) if not isinstance(raw_max, int) else raw_max
        max_iter = max(1, min(int(mi), 1000))
    else:
        max_iter = max(1, min(definition.max_iterations, 1000))
    agent_id_str = str(definition.agent_id)
    correlation_id = run.correlation_id
    project_id = run.project_id
    settings = get_settings()
    api_base = settings.api_url.rstrip("/")
    agent_hdr = str(definition.agent_id)
    token_cap = max(1, definition.max_tokens_per_run)
    cumulative_tokens = 0
    llm_rounds = 0
    collected_receipt_ids: list[str] = []
    collected_artifacts: list[dict[str, Any]] = []

    last_assistant_text = ""
    for iteration in range(max_iter):
        if cumulative_tokens >= token_cap:
            return {
                "ok": True,
                "final_text": last_assistant_text,
                "iterations": llm_rounds,
                "total_tokens": cumulative_tokens,
                "truncated": True,
                "truncation_reason": "max_tokens_per_run",
                "receipt_ids": collected_receipt_ids,
                "artifacts": collected_artifacts,
            }
        if event_sink is not None:
            await event_sink(
                {
                    "type": "react_iteration",
                    "iteration": iteration,
                    "run_id": str(run.id),
                }
            )
        try:
            data, step_receipt_id = await _post_gateway_completion(
                httpx_client=httpx_client,
                gateway_api_key=gateway_api_key,
                provider=provider,
                model=definition.model,
                messages=messages,
                x_axiom_agent_id=agent_hdr,
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("react.llm_step_failed", error=str(exc))
            return {
                "ok": False,
                "error": "llm_step_failed",
                "detail": str(exc),
                "total_tokens": cumulative_tokens,
                "receipt_ids": collected_receipt_ids,
                "artifacts": collected_artifacts,
            }

        if step_receipt_id:
            collected_receipt_ids.append(step_receipt_id)

        step_tokens = _usage_tokens_from_response(data, provider)
        cumulative_tokens += step_tokens
        llm_rounds += 1

        text = _extract_text_from_response(data)
        last_assistant_text = text
        messages.append({"role": "assistant", "content": text})

        if cumulative_tokens >= token_cap:
            return {
                "ok": True,
                "final_text": last_assistant_text,
                "iterations": llm_rounds,
                "total_tokens": cumulative_tokens,
                "truncated": True,
                "truncation_reason": "max_tokens_per_run",
                "receipt_ids": collected_receipt_ids,
                "artifacts": collected_artifacts,
            }

        parsed = _parse_react_response(text)

        if parsed["type"] == "final_answer":
            return {
                "ok": True,
                "final_text": str(parsed["text"]),
                "iterations": llm_rounds,
                "total_tokens": cumulative_tokens,
                "receipt_ids": collected_receipt_ids,
                "artifacts": collected_artifacts,
            }

        # parsed["type"] == "action"
        name = str(parsed["name"])
        args = dict(parsed["args"]) if isinstance(parsed.get("args"), dict) else {}

        ctx = ToolExecutionContext(
            project_id=project_id,
            agent_id=agent_id_str,
            correlation_id=correlation_id,
            api_base_url=api_base,
            api_key=gateway_api_key,
            httpx_client=httpx_client,
            run_id=run.id,
        )
        try:
            result = await dispatch_tool(name, ctx, **args)
            if isinstance(result, dict) and result.get("ok") is True and name == "file_write":
                entry = _artifact_entry_for_file_write(
                    project_id=project_id,
                    run_id=run.id,
                    args=args,
                    result=result,
                )
                if entry is not None:
                    collected_artifacts.append(entry)
            observation = json.dumps({"ok": True, "result": result}, separators=(",", ":"))
        except ToolDenied as denied:
            observation = json.dumps(
                {
                    "ok": False,
                    "denied": True,
                    "receipt_id": denied.receipt_id,
                    "reason": denied.reason,
                },
                separators=(",", ":"),
            )
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    return {
        "ok": True,
        "final_text": last_assistant_text,
        "iterations": llm_rounds,
        "total_tokens": cumulative_tokens,
        "receipt_ids": collected_receipt_ids,
        "artifacts": collected_artifacts,
        "truncated": True,
        "truncation_reason": "max_iterations",
    }
