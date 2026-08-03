"""Record intercepted HTTP calls for governance reports (no secrets in stored data)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_SENSITIVE_QUERY_KEYS = re.compile(
    r"(key|token|secret|password|auth)",
    re.IGNORECASE,
)


def sanitize_url_for_report(url: str) -> str:
    """Strip query parameters whose names suggest secrets (keys, tokens)."""
    parsed = urlparse(str(url))
    if not parsed.query:
        return str(url)
    pairs = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        if _SENSITIVE_QUERY_KEYS.search(k):
            pairs.append((k, "[redacted]"))
        else:
            pairs.append((k, v))
    new_query = urlencode(pairs)
    return urlunparse(parsed._replace(query=new_query))


@dataclass
class RecordedCall:
    timestamp: str
    method: str
    url: str
    action_type: str
    target: str
    risk: str
    verdict: str
    receipt_id: str | None
    status_code: int | None
    error: str | None
    duration_ms: float | None
    body_hash: str | None = None
    authorization_header_present: bool | None = None


class GovernanceRecorder:
    """Accumulates governance events for JSON report output."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.calls: list[RecordedCall] = []
        self.start_time = datetime.now(timezone.utc)

    def record_call(
        self,
        *,
        method: str,
        url: str,
        action_type: str,
        target: str,
        risk: str,
        verdict: str,
        receipt_id: str | None,
        body_hash: str | None = None,
        authorization_header_present: bool | None = None,
    ) -> None:
        safe_url = sanitize_url_for_report(url)
        safe_target = sanitize_url_for_report(target)[:500]
        self.calls.append(
            RecordedCall(
                timestamp=datetime.now(timezone.utc).isoformat(),
                method=method,
                url=safe_url,
                action_type=action_type,
                target=safe_target,
                risk=risk,
                verdict=verdict,
                receipt_id=receipt_id,
                status_code=None,
                error=None,
                duration_ms=None,
                body_hash=body_hash,
                authorization_header_present=authorization_header_present,
            )
        )

    def record_outcome(self, receipt_id: str, status_code: int) -> None:
        for c in reversed(self.calls):
            if c.receipt_id == receipt_id and c.status_code is None:
                c.status_code = status_code
                return

    def record_error(
        self,
        *,
        method: str,
        url: str,
        error: str,
        action_type: str = "tool.http",
        target: str = "",
        risk: str = "low",
    ) -> None:
        safe_url = sanitize_url_for_report(url)
        self.calls.append(
            RecordedCall(
                timestamp=datetime.now(timezone.utc).isoformat(),
                method=method,
                url=safe_url,
                action_type=action_type,
                target=sanitize_url_for_report(target)[:500] if target else "",
                risk=risk,
                verdict="error",
                receipt_id=None,
                status_code=None,
                error=error,
                duration_ms=None,
                body_hash=None,
                authorization_header_present=None,
            )
        )

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def allowed_count(self) -> int:
        return sum(1 for c in self.calls if c.verdict == "allow")

    @property
    def denied_count(self) -> int:
        return sum(1 for c in self.calls if c.verdict == "deny")

    @property
    def held_count(self) -> int:
        return sum(1 for c in self.calls if c.verdict == "hold")

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.calls if c.verdict == "error")

    def _unique_targets(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for c in self.calls:
            t = c.target
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return sorted(out)

    def _action_type_breakdown(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.calls:
            counts[c.action_type] = counts.get(c.action_type, 0) + 1
        return dict(sorted(counts.items()))

    def finalize(self) -> dict[str, Any]:
        from ._version import __version__

        return {
            "axiom_version": __version__,
            "agent_id": self.agent_id,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "total_calls": self.total_calls,
            "summary": {
                "allowed": self.allowed_count,
                "denied": self.denied_count,
                "held": self.held_count,
                "errors": self.error_count,
            },
            "calls": [asdict(c) for c in self.calls],
            "unique_targets": self._unique_targets(),
            "action_type_breakdown": self._action_type_breakdown(),
        }
