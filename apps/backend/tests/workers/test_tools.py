"""Phase 6.5 — tool registry, SSRF matrix, and dispatch."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_httpx

from axiom.core.security import UnsafeUrlError
from axiom.workers.tools import dispatch_tool
from axiom.workers.tools.base import ToolExecutionContext
from axiom.workers.tools.http_fetch import HttpFetchTool, assert_safe_fetch_url

GOVERN_URL = "http://axiom.test/v1/governance/govern"


def _govern_json() -> dict[str, object]:
    return {
        "receipt_id": "019da4ea-0000-7000-8000-000000000001",
        "verdict": "allow",
        "reason": None,
        "policy_version": "1",
        "risk_assessed": "medium",
        "mode": "enforce",
        "chain_id": None,
        "approval_status": None,
        "approval_expires_at": None,
    }


@pytest.fixture
def tool_ctx() -> ToolExecutionContext:
    return ToolExecutionContext(
        project_id=uuid4(),
        agent_id="019da4ea-aaaa-7000-8000-0000000000aa",
        correlation_id="corr-test",
        api_base_url="http://axiom.test",
        api_key="test-project-api-key",
        httpx_client=httpx.AsyncClient(),
        run_id=uuid4(),
    )


def test_tools_module_exports_dispatch() -> None:
    import axiom.workers.tools as mod

    assert hasattr(mod, "dispatch_tool")
    assert callable(mod.dispatch_tool)


@pytest.mark.asyncio
async def test_dispatch_http_fetch_public_ok(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=GOVERN_URL, json=_govern_json())
    httpx_mock.add_response(
        method="GET",
        url="http://1.1.1.1/hello",
        text="ok",
        status_code=200,
    )
    ctx = ToolExecutionContext(
        project_id=uuid4(),
        agent_id="019da4ea-aaaa-7000-8000-0000000000aa",
        correlation_id="corr-test",
        api_base_url="http://axiom.test",
        api_key="test-project-api-key",
        httpx_client=httpx.AsyncClient(),
        run_id=uuid4(),
    )
    out = await dispatch_tool("http_fetch", ctx, url="http://1.1.1.1/hello")
    assert out.get("ok") is True
    assert out.get("body_preview") == "ok"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://172.17.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/",
        "http://[::1]/",
        "http://[fd00::1]/",
        "http://[fe80::1]/",
    ],
)
@pytest.mark.asyncio
async def test_ssrf_matrix_blocked(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        await assert_safe_fetch_url(url)


@pytest.mark.asyncio
async def test_ssrf_redirect_to_loopback_blocked(
    httpx_mock: pytest_httpx.HTTPXMock, tool_ctx: ToolExecutionContext
) -> None:
    httpx_mock.add_response(method="POST", url=GOVERN_URL, json=_govern_json())
    httpx_mock.add_response(
        method="GET",
        url="http://1.1.1.1/trap",
        status_code=302,
        headers={"Location": "http://127.0.0.1/owned"},
    )
    tool = HttpFetchTool()
    out = await tool.execute(tool_ctx, url="http://1.1.1.1/trap")
    assert out.get("ok") is False
    assert out.get("error") == "ssrf_blocked"


@pytest.mark.asyncio
async def test_web_search_disabled_without_key(
    httpx_mock: pytest_httpx.HTTPXMock, tool_ctx: ToolExecutionContext
) -> None:
    httpx_mock.add_response(method="POST", url=GOVERN_URL, json=_govern_json())
    out = await dispatch_tool("web_search", tool_ctx, query="hello world")
    assert out.get("disabled") is True
    assert out.get("results") == []


@pytest.mark.asyncio
async def test_file_write_artifact(
    httpx_mock: pytest_httpx.HTTPXMock,
    tool_ctx: ToolExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    httpx_mock.add_response(method="POST", url=GOVERN_URL, json=_govern_json())
    import axiom.workers.tools.file_write as fw

    monkeypatch.setattr(fw, "DEFAULT_ARTIFACTS_ROOT", tmp_path)
    out = await dispatch_tool(
        "file_write",
        tool_ctx,
        filename="notes.txt",
        content="hello",
    )
    assert out.get("ok") is True
    assert tool_ctx.run_id is not None
    written = tmp_path / str(tool_ctx.run_id) / "notes.txt"
    assert written.read_text() == "hello"
