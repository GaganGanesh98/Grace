"""HTTP-level governance interception for ``requests`` and ``httpx`` (reversible monkey-patches)."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from typing import Any, Callable
from urllib.parse import urlparse

from .client import default_client
from .config import get_config
from .exceptions import GovernanceDenied, GovernanceHeld

# Known LLM API patterns → (action_type, default_risk)
LLM_PATTERNS: dict[str, tuple[str, str]] = {
    "api.openai.com": ("tool.llm.openai", "low"),
    "api.anthropic.com": ("tool.llm.anthropic", "low"),
    "generativelanguage.googleapis.com": ("tool.llm.google", "low"),
    "api.groq.com": ("tool.llm.groq", "low"),
    "api.together.xyz": ("tool.llm.together", "low"),
    "api.x.ai": ("tool.llm.xai", "low"),
}

# Substring patterns → action_type (high-risk messaging)
HIGH_RISK_PATTERNS: dict[str, str] = {
    "smtp": "tool.email.send",
    "gmail.googleapis.com": "tool.email.send",
    "graph.microsoft.com/v1.0/me/sendmail": "tool.email.send",
    "api.slack.com/chat.postmessage": "tool.chat.send",
    "hooks.slack.com": "tool.webhook",
}


class MaxRuntimeExceeded(Exception):
    """Raised when ``--max-runtime`` is exceeded."""


def _body_bytes(body: Any) -> bytes | None:
    if body is None:
        return None
    if isinstance(body, bytes):
        return body
    if isinstance(body, (bytearray, memoryview)):
        return bytes(body)
    return None


def _hash_body(body: Any) -> str | None:
    raw = _body_bytes(body)
    if raw is None or len(raw) == 0:
        return None
    return hashlib.sha256(raw).hexdigest()[:16]


def _headers_have_authorization(headers: Any) -> bool | None:
    if headers is None:
        return None
    try:
        for k in headers:
            if str(k).lower() == "authorization":
                return True
        return False
    except Exception:
        return None


class HttpInterceptor:
    """Monkey-patch HTTP libraries to route outbound calls through ``axiom.govern`` / ``axiom.report``."""

    def __init__(
        self,
        agent_id: str,
        mode: str,
        recorder: Any,
        workflow: str | None = None,
        max_cost: float | None = None,
        max_runtime: float | None = None,
        verbose: bool = False,
    ) -> None:
        self.agent_id = agent_id
        self.mode = mode
        self.recorder = recorder
        self.workflow = workflow
        self.max_cost = max_cost
        self.max_runtime = max_runtime
        self.verbose = verbose
        self._originals: list[tuple[Any, str, Any]] = []
        self._installed = False
        self._total_cost = 0.0
        self._run_started = time.monotonic()

    def _axiom_base_netloc(self) -> str | None:
        try:
            cfg = get_config()
            return urlparse(cfg.base_url).netloc.lower() or None
        except Exception:
            return None

    def _is_axiom_api_call(self, url: Any) -> bool:
        base = self._axiom_base_netloc()
        if not base:
            return False
        parsed = urlparse(str(url))
        return parsed.netloc.lower() == base

    def _classify_action(self, method: str, url: str) -> str:
        parsed = urlparse(str(url))
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        combined = f"{host}{path}"

        for pattern, (action_type, _) in LLM_PATTERNS.items():
            if pattern in host:
                return action_type

        for pattern, action_type in HIGH_RISK_PATTERNS.items():
            if pattern in host or pattern in combined:
                return action_type

        method_upper = method.upper()
        if method_upper in ("GET", "HEAD", "OPTIONS"):
            return "tool.http.read"
        if method_upper in ("POST", "PUT", "PATCH"):
            return "tool.http.write"
        if method_upper == "DELETE":
            return "tool.http.delete"
        return "tool.http"

    def _assess_risk(self, method: str, url: str, body: Any) -> str:
        parsed = urlparse(str(url))
        host = parsed.netloc.lower()

        for pattern, (_, risk) in LLM_PATTERNS.items():
            if pattern in host:
                return risk

        for pattern in HIGH_RISK_PATTERNS:
            if pattern in host:
                return "high"

        if method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            return "medium"
        return "low"

    def _extract_target(self, url: str) -> str:
        parsed = urlparse(str(url))
        return f"{parsed.netloc}{parsed.path}"[:500]

    def _check_cost_limit_before(self) -> None:
        if self.max_cost is not None and self._total_cost >= self.max_cost:
            raise GovernanceDenied(
                verdict="deny",
                reason=(
                    f"Cost limit exceeded: ${self._total_cost:.4f} >= ${self.max_cost:.4f}"
                ),
                receipt_id="cost-limit",
            )

    def _check_cost_limit_after(self) -> None:
        if self.max_cost is not None and self._total_cost >= self.max_cost:
            raise ConnectionError(
                f"AXIOM governance: Cost limit exceeded: ${self._total_cost:.4f} >= "
                f"${self.max_cost:.4f} (receipt: cost-limit)"
            )

    def _vlog(self, msg: str) -> None:
        if self.verbose:
            print(msg, file=sys.stderr)

    def _check_runtime_limit(self) -> None:
        if self.max_runtime is None:
            return
        elapsed = time.monotonic() - self._run_started
        if elapsed >= self.max_runtime:
            raise MaxRuntimeExceeded(
                f"Max runtime exceeded: {elapsed:.1f}s >= {self.max_runtime:.1f}s"
            )

    def _apply_cost_from_response_body(self, content: bytes | None) -> None:
        if not content:
            return
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeError):
            return
        if not isinstance(data, dict):
            return
        usage = data.get("usage")
        if isinstance(usage, dict):
            for key in ("total_cost", "cost", "cost_usd"):
                v = usage.get(key)
                if isinstance(v, (int, float)):
                    self._total_cost += float(v)
                    return
        for key in ("total_cost", "cost_usd"):
            v = data.get(key)
            if isinstance(v, (int, float)):
                self._total_cost += float(v)
                return

    def install(self) -> None:
        if self._installed:
            return

        try:
            import requests

            orig = requests.Session.send
            self._originals.append((requests.Session, "send", orig))
            requests.Session.send = self._make_requests_wrapper(orig)
        except ImportError:
            pass

        try:
            import httpx

            o1 = httpx.Client.send
            self._originals.append((httpx.Client, "send", o1))
            httpx.Client.send = self._make_httpx_sync_wrapper(o1)

            o2 = httpx.AsyncClient.send
            self._originals.append((httpx.AsyncClient, "send", o2))
            httpx.AsyncClient.send = self._make_httpx_async_wrapper(o2)
        except ImportError:
            pass

        self._installed = True

    def uninstall(self) -> None:
        for owner, attr, original in reversed(self._originals):
            setattr(owner, attr, original)
        self._originals.clear()
        self._installed = False

    def _govern_and_record_requests(
        self,
        original_send: Callable[..., Any],
        session_self: Any,
        request: Any,
        **kwargs: Any,
    ) -> Any:
        self._check_runtime_limit()
        url = getattr(request, "url", "")
        if self._is_axiom_api_call(url):
            return original_send(session_self, request, **kwargs)

        method = getattr(request, "method", "GET") or "GET"
        body = getattr(request, "body", None)
        action_type = self._classify_action(method, str(url))
        target = self._extract_target(str(url))
        risk = self._assess_risk(method, str(url), body)
        body_hash = _hash_body(body)
        auth_present = _headers_have_authorization(getattr(request, "headers", None))

        enforce = self.mode == "enforce"

        try:
            self._check_cost_limit_before()

            if self.mode == "learn":
                result = default_client().govern(
                    agent_id=self.agent_id,
                    action_type=action_type,
                    target=target,
                    risk=risk,
                    enforce=False,
                    workflow=self.workflow,
                )
                self.recorder.record_call(
                    method=method,
                    url=str(url),
                    action_type=action_type,
                    target=target,
                    risk=risk,
                    verdict=result.verdict,
                    receipt_id=result.receipt_id or None,
                    body_hash=body_hash,
                    authorization_header_present=auth_present,
                )
                self._vlog(
                    f"[axiom] govern verdict={result.verdict} action={action_type} target={target}"
                )
                response = original_send(session_self, request, **kwargs)
                self._apply_cost_from_response_body(
                    getattr(response, "content", None)
                    if hasattr(response, "content")
                    else None
                )
                if result.receipt_id:
                    default_client().report(
                        receipt_id=result.receipt_id,
                        outcome={
                            "status_code": getattr(response, "status_code", 0),
                            "content_length": len(response.content or b""),
                        },
                    )
                    self.recorder.record_outcome(
                        result.receipt_id,
                        int(getattr(response, "status_code", 0) or 0),
                    )
                self._check_cost_limit_after()
                return response

            result = default_client().govern(
                agent_id=self.agent_id,
                action_type=action_type,
                target=target,
                risk=risk,
                enforce=True,
                workflow=self.workflow,
            )
            self.recorder.record_call(
                method=method,
                url=str(url),
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="allow",
                receipt_id=result.receipt_id or None,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            self._vlog(f"[axiom] govern verdict=allow action={action_type} target={target}")
            response = original_send(session_self, request, **kwargs)
            self._apply_cost_from_response_body(getattr(response, "content", None))
            if result.receipt_id:
                default_client().report(
                    receipt_id=result.receipt_id,
                    outcome={
                        "status_code": getattr(response, "status_code", 0),
                        "content_length": len(response.content or b""),
                    },
                )
                self.recorder.record_outcome(
                    result.receipt_id,
                    int(getattr(response, "status_code", 0) or 0),
                )
            self._check_cost_limit_after()
            return response

        except GovernanceDenied as e:
            self._vlog(f"[axiom] govern verdict=deny action={action_type} target={target}")
            self.recorder.record_call(
                method=method,
                url=str(url),
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="deny",
                receipt_id=e.receipt_id,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            if e.receipt_id == "cost-limit":
                raise ConnectionError(
                    f"AXIOM governance: {e.reason} (receipt: {e.receipt_id})"
                ) from e
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance denied: {action_type} → {target} "
                    f"(receipt: {e.receipt_id})"
                ) from e
            response = original_send(session_self, request, **kwargs)
            return response

        except GovernanceHeld as e:
            self._vlog(f"[axiom] govern verdict=hold action={action_type} target={target}")
            self.recorder.record_call(
                method=method,
                url=str(url),
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="hold",
                receipt_id=e.receipt_id,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance held: {action_type} → {target} "
                    f"(approve at dashboard, receipt: {e.receipt_id})"
                ) from e
            response = original_send(session_self, request, **kwargs)
            return response

        except MaxRuntimeExceeded as e:
            self.recorder.record_error(method=method, url=str(url), error=str(e))
            raise

        except Exception as e:
            self.recorder.record_error(method=method, url=str(url), error=str(e))
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance unavailable: {e}. Failing closed (enforce mode)."
                ) from e
            return original_send(session_self, request, **kwargs)

    def _make_requests_wrapper(self, original_send: Any) -> Any:
        interceptor = self

        def governed_send(session_self: Any, request: Any, **kwargs: Any) -> Any:
            return interceptor._govern_and_record_requests(
                original_send, session_self, request, **kwargs
            )

        return governed_send

    def _govern_and_record_httpx_sync(
        self,
        original_send: Callable[..., Any],
        client_self: Any,
        request: Any,
        **kwargs: Any,
    ) -> Any:
        self._check_runtime_limit()
        url = getattr(request, "url", "")
        ustr = str(url)
        if self._is_axiom_api_call(ustr):
            return original_send(client_self, request, **kwargs)

        method = getattr(request, "method", "GET") or "GET"
        body = getattr(request, "content", None)
        action_type = self._classify_action(method, ustr)
        target = self._extract_target(ustr)
        risk = self._assess_risk(method, ustr, body)
        body_hash = _hash_body(body)
        auth_present = _headers_have_authorization(getattr(request, "headers", None))

        enforce = self.mode == "enforce"

        try:
            self._check_cost_limit_before()

            if self.mode == "learn":
                result = default_client().govern(
                    agent_id=self.agent_id,
                    action_type=action_type,
                    target=target,
                    risk=risk,
                    enforce=False,
                    workflow=self.workflow,
                )
                self.recorder.record_call(
                    method=method,
                    url=ustr,
                    action_type=action_type,
                    target=target,
                    risk=risk,
                    verdict=result.verdict,
                    receipt_id=result.receipt_id or None,
                    body_hash=body_hash,
                    authorization_header_present=auth_present,
                )
                response = original_send(client_self, request, **kwargs)
                self._apply_cost_from_response_body(getattr(response, "content", None))
                if result.receipt_id:
                    default_client().report(
                        receipt_id=result.receipt_id,
                        outcome={
                            "status_code": getattr(response, "status_code", 0),
                            "content_length": len(response.content or b""),
                        },
                    )
                    self.recorder.record_outcome(
                        result.receipt_id,
                        int(getattr(response, "status_code", 0) or 0),
                    )
                self._check_cost_limit_after()
                return response

            result = default_client().govern(
                agent_id=self.agent_id,
                action_type=action_type,
                target=target,
                risk=risk,
                enforce=True,
                workflow=self.workflow,
            )
            self.recorder.record_call(
                method=method,
                url=ustr,
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="allow",
                receipt_id=result.receipt_id or None,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            response = original_send(client_self, request, **kwargs)
            self._apply_cost_from_response_body(getattr(response, "content", None))
            if result.receipt_id:
                default_client().report(
                    receipt_id=result.receipt_id,
                    outcome={
                        "status_code": getattr(response, "status_code", 0),
                        "content_length": len(response.content or b""),
                    },
                )
                self.recorder.record_outcome(
                    result.receipt_id,
                    int(getattr(response, "status_code", 0) or 0),
                )
            self._check_cost_limit_after()
            return response

        except GovernanceDenied as e:
            self.recorder.record_call(
                method=method,
                url=ustr,
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="deny",
                receipt_id=e.receipt_id,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            if e.receipt_id == "cost-limit":
                raise ConnectionError(
                    f"AXIOM governance: {e.reason} (receipt: {e.receipt_id})"
                ) from e
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance denied: {action_type} → {target} "
                    f"(receipt: {e.receipt_id})"
                ) from e
            return original_send(client_self, request, **kwargs)

        except GovernanceHeld as e:
            self.recorder.record_call(
                method=method,
                url=ustr,
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="hold",
                receipt_id=e.receipt_id,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance held: {action_type} → {target} "
                    f"(approve at dashboard, receipt: {e.receipt_id})"
                ) from e
            return original_send(client_self, request, **kwargs)

        except MaxRuntimeExceeded as e:
            self.recorder.record_error(method=method, url=ustr, error=str(e))
            raise

        except Exception as e:
            self.recorder.record_error(method=method, url=ustr, error=str(e))
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance unavailable: {e}. Failing closed (enforce mode)."
                ) from e
            return original_send(client_self, request, **kwargs)

    def _make_httpx_sync_wrapper(self, original_send: Any) -> Any:
        interceptor = self

        def governed_send(client_self: Any, request: Any, **kwargs: Any) -> Any:
            return interceptor._govern_and_record_httpx_sync(
                original_send, client_self, request, **kwargs
            )

        return governed_send

    async def _govern_and_record_httpx_async(
        self,
        original_send: Any,
        client_self: Any,
        request: Any,
        **kwargs: Any,
    ) -> Any:
        self._check_runtime_limit()
        url = getattr(request, "url", "")
        ustr = str(url)
        if self._is_axiom_api_call(ustr):
            return await original_send(client_self, request, **kwargs)

        method = getattr(request, "method", "GET") or "GET"
        body = getattr(request, "content", None)
        action_type = self._classify_action(method, ustr)
        target = self._extract_target(ustr)
        risk = self._assess_risk(method, ustr, body)
        body_hash = _hash_body(body)
        auth_present = _headers_have_authorization(getattr(request, "headers", None))

        enforce = self.mode == "enforce"

        try:
            self._check_cost_limit_before()

            if self.mode == "learn":
                result = default_client().govern(
                    agent_id=self.agent_id,
                    action_type=action_type,
                    target=target,
                    risk=risk,
                    enforce=False,
                    workflow=self.workflow,
                )
                self.recorder.record_call(
                    method=method,
                    url=ustr,
                    action_type=action_type,
                    target=target,
                    risk=risk,
                    verdict=result.verdict,
                    receipt_id=result.receipt_id or None,
                    body_hash=body_hash,
                    authorization_header_present=auth_present,
                )
                response = await original_send(client_self, request, **kwargs)
                self._apply_cost_from_response_body(getattr(response, "content", None))
                if result.receipt_id:
                    default_client().report(
                        receipt_id=result.receipt_id,
                        outcome={
                            "status_code": getattr(response, "status_code", 0),
                            "content_length": len(response.content or b""),
                        },
                    )
                    self.recorder.record_outcome(
                        result.receipt_id,
                        int(getattr(response, "status_code", 0) or 0),
                    )
                self._check_cost_limit_after()
                return response

            result = default_client().govern(
                agent_id=self.agent_id,
                action_type=action_type,
                target=target,
                risk=risk,
                enforce=True,
                workflow=self.workflow,
            )
            self.recorder.record_call(
                method=method,
                url=ustr,
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="allow",
                receipt_id=result.receipt_id or None,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            response = await original_send(client_self, request, **kwargs)
            self._apply_cost_from_response_body(getattr(response, "content", None))
            if result.receipt_id:
                default_client().report(
                    receipt_id=result.receipt_id,
                    outcome={
                        "status_code": getattr(response, "status_code", 0),
                        "content_length": len(response.content or b""),
                    },
                )
                self.recorder.record_outcome(
                    result.receipt_id,
                    int(getattr(response, "status_code", 0) or 0),
                )
            self._check_cost_limit_after()
            return response

        except GovernanceDenied as e:
            self.recorder.record_call(
                method=method,
                url=ustr,
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="deny",
                receipt_id=e.receipt_id,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            if e.receipt_id == "cost-limit":
                raise ConnectionError(
                    f"AXIOM governance: {e.reason} (receipt: {e.receipt_id})"
                ) from e
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance denied: {action_type} → {target} "
                    f"(receipt: {e.receipt_id})"
                ) from e
            return await original_send(client_self, request, **kwargs)

        except GovernanceHeld as e:
            self.recorder.record_call(
                method=method,
                url=ustr,
                action_type=action_type,
                target=target,
                risk=risk,
                verdict="hold",
                receipt_id=e.receipt_id,
                body_hash=body_hash,
                authorization_header_present=auth_present,
            )
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance held: {action_type} → {target} "
                    f"(approve at dashboard, receipt: {e.receipt_id})"
                ) from e
            return await original_send(client_self, request, **kwargs)

        except MaxRuntimeExceeded as e:
            self.recorder.record_error(method=method, url=ustr, error=str(e))
            raise

        except Exception as e:
            self.recorder.record_error(method=method, url=ustr, error=str(e))
            if enforce:
                raise ConnectionError(
                    f"AXIOM governance unavailable: {e}. Failing closed (enforce mode)."
                ) from e
            return await original_send(client_self, request, **kwargs)

    def _make_httpx_async_wrapper(self, original_send: Any) -> Any:
        interceptor = self

        async def governed_send(client_self: Any, request: Any, **kwargs: Any) -> Any:
            return await interceptor._govern_and_record_httpx_async(
                original_send, client_self, request, **kwargs
            )

        return governed_send
