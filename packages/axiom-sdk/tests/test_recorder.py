"""Tests for :mod:`axiom.recorder`."""

from __future__ import annotations

from axiom.recorder import GovernanceRecorder, sanitize_url_for_report


def test_record_call_stores_all_fields() -> None:
    r = GovernanceRecorder(agent_id="a1")
    r.record_call(
        method="GET",
        url="https://example.com/p?token=secret",
        action_type="tool.http.read",
        target="example.com/p",
        risk="low",
        verdict="allow",
        receipt_id="r1",
        body_hash="abc123",
        authorization_header_present=True,
    )
    assert len(r.calls) == 1
    c = r.calls[0]
    assert c.method == "GET"
    assert "redacted" in c.url.lower()
    assert c.action_type == "tool.http.read"
    assert c.verdict == "allow"
    assert c.receipt_id == "r1"
    assert c.body_hash == "abc123"
    assert c.authorization_header_present is True


def test_record_outcome_updates_status_code() -> None:
    r = GovernanceRecorder(agent_id="a1")
    r.record_call(
        method="POST",
        url="https://x.com/",
        action_type="tool.http.write",
        target="x.com/",
        risk="medium",
        verdict="allow",
        receipt_id="r2",
    )
    r.record_outcome("r2", 201)
    assert r.calls[0].status_code == 201


def test_record_error_increments_error_count() -> None:
    r = GovernanceRecorder(agent_id="a1")
    r.record_error(method="GET", url="https://z.com", error="boom")
    assert r.error_count == 1
    assert r.calls[0].verdict == "error"


def test_finalize_returns_complete_report() -> None:
    r = GovernanceRecorder(agent_id="bot")
    r.record_call(
        method="GET",
        url="https://a.com/",
        action_type="tool.http.read",
        target="a.com/",
        risk="low",
        verdict="allow",
        receipt_id="x",
    )
    rep = r.finalize()
    assert rep["agent_id"] == "bot"
    assert rep["total_calls"] == 1
    assert "summary" in rep
    assert "calls" in rep
    assert "unique_targets" in rep
    assert "action_type_breakdown" in rep


def test_action_type_breakdown_groups_correctly() -> None:
    r = GovernanceRecorder(agent_id="a1")
    for _ in range(2):
        r.record_call(
            method="GET",
            url="https://a/",
            action_type="tool.llm.openai",
            target="a/",
            risk="low",
            verdict="allow",
            receipt_id=None,
        )
    r.record_call(
        method="GET",
        url="https://b/",
        action_type="tool.http.read",
        target="b/",
        risk="low",
        verdict="allow",
        receipt_id=None,
    )
    br = r._action_type_breakdown()
    assert br["tool.llm.openai"] == 2
    assert br["tool.http.read"] == 1


def test_unique_targets_deduplicates() -> None:
    r = GovernanceRecorder(agent_id="a1")
    r.record_call(
        method="GET",
        url="https://same/path",
        action_type="tool.http.read",
        target="same/path",
        risk="low",
        verdict="allow",
        receipt_id="1",
    )
    r.record_call(
        method="GET",
        url="https://same/path",
        action_type="tool.http.read",
        target="same/path",
        risk="low",
        verdict="allow",
        receipt_id="2",
    )
    assert r._unique_targets() == ["same/path"]


def test_counts_match_recorded_calls() -> None:
    r = GovernanceRecorder(agent_id="a1")
    r.record_call(
        method="GET",
        url="https://a/",
        action_type="t",
        target="a/",
        risk="low",
        verdict="allow",
        receipt_id=None,
    )
    r.record_call(
        method="GET",
        url="https://b/",
        action_type="t",
        target="b/",
        risk="low",
        verdict="deny",
        receipt_id=None,
    )
    r.record_call(
        method="GET",
        url="https://c/",
        action_type="t",
        target="c/",
        risk="low",
        verdict="hold",
        receipt_id=None,
    )
    r.record_error(method="GET", url="https://e/", error="x")
    assert r.total_calls == 4
    assert r.allowed_count == 1
    assert r.denied_count == 1
    assert r.held_count == 1
    assert r.error_count == 1


def test_sanitize_url_strips_sensitive_query_names() -> None:
    u = sanitize_url_for_report("https://ex.com/x?api_key=sekret&foo=bar")
    assert "sekret" not in u
    assert "redacted" in u.lower()
    assert "foo=bar" in u
