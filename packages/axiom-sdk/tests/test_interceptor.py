"""Tests for :mod:`axiom.interceptor`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
import responses

import axiom
from axiom.exceptions import GovernanceDenied, GovernanceHeld
from axiom.interceptor import HttpInterceptor
from axiom.recorder import GovernanceRecorder


@pytest.fixture
def base_url() -> str:
    return "http://axiom.test"


def test_install_patches_requests_session_send(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    orig = requests.Session.send
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="learn", recorder=rec)
    ix.install()
    assert requests.Session.send is not orig
    ix.uninstall()
    assert requests.Session.send is orig


def test_install_patches_httpx_client_send(base_url: str) -> None:
    httpx = pytest.importorskip("httpx")
    axiom.init(api_key="k", base_url=base_url)
    orig = httpx.Client.send
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="learn", recorder=rec)
    ix.install()
    assert httpx.Client.send is not orig
    ix.uninstall()
    assert httpx.Client.send is orig


def test_uninstall_restores_originals(base_url: str) -> None:
    axiom.init(api_key="k", base_url=base_url)
    r0 = requests.Session.send
    ix = HttpInterceptor("a", "learn", GovernanceRecorder("a"))
    ix.install()
    ix.uninstall()
    assert requests.Session.send is r0


@responses.activate
def test_axiom_api_calls_are_skipped(base_url: str) -> None:
    responses.add(responses.GET, f"{base_url}/v1/governance/ping", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="learn", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            gov = MagicMock()
            rep = MagicMock()
            dc.return_value.govern = gov
            dc.return_value.report = rep
            sess = requests.Session()
            sess.get(f"{base_url}/v1/governance/ping")
            gov.assert_not_called()
    finally:
        ix.uninstall()


@responses.activate
def test_learn_mode_allows_all_calls(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="learn", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            gr = MagicMock()
            gr.verdict = "deny"
            gr.receipt_id = "r1"
            dc.return_value.govern = MagicMock(return_value=gr)
            dc.return_value.report = MagicMock()
            sess = requests.Session()
            r = sess.get("https://httpbin.org/get")
            assert r.status_code == 200
    finally:
        ix.uninstall()


@responses.activate
def test_learn_mode_records_every_call(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="learn", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            gr = MagicMock()
            gr.verdict = "allow"
            gr.receipt_id = "r9"
            dc.return_value.govern = MagicMock(return_value=gr)
            dc.return_value.report = MagicMock()
            requests.Session().get("https://httpbin.org/get")
            assert rec.total_calls >= 1
    finally:
        ix.uninstall()


@responses.activate
def test_enforce_mode_allows_governed_calls(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="enforce", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            gr = MagicMock()
            gr.verdict = "allow"
            gr.receipt_id = "r1"
            dc.return_value.govern = MagicMock(return_value=gr)
            dc.return_value.report = MagicMock()
            r = requests.Session().get("https://httpbin.org/get")
            assert r.status_code == 200
    finally:
        ix.uninstall()


@responses.activate
def test_enforce_mode_raises_on_deny(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="enforce", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            dc.return_value.govern = MagicMock(
                side_effect=GovernanceDenied("deny", "no", "rid-deny")
            )
            dc.return_value.report = MagicMock()
            with pytest.raises(ConnectionError):
                requests.Session().get("https://httpbin.org/get")
    finally:
        ix.uninstall()


@responses.activate
def test_enforce_mode_raises_on_hold(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="enforce", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            dc.return_value.govern = MagicMock(side_effect=GovernanceHeld("rid-hold"))
            dc.return_value.report = MagicMock()
            with pytest.raises(ConnectionError):
                requests.Session().get("https://httpbin.org/get")
    finally:
        ix.uninstall()


def test_classify_openai_as_llm() -> None:
    axiom.init(api_key="k", base_url="http://t")
    ix = HttpInterceptor("a", "learn", GovernanceRecorder("a"))
    assert ix._classify_action("POST", "https://api.openai.com/v1/chat/completions") == "tool.llm.openai"


def test_classify_anthropic_as_llm() -> None:
    axiom.init(api_key="k", base_url="http://t")
    ix = HttpInterceptor("a", "learn", GovernanceRecorder("a"))
    assert ix._classify_action("POST", "https://api.anthropic.com/v1/messages") == "tool.llm.anthropic"


def test_classify_gmail_as_email_high_risk() -> None:
    axiom.init(api_key="k", base_url="http://t")
    ix = HttpInterceptor("a", "learn", GovernanceRecorder("a"))
    assert ix._classify_action("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send") == "tool.email.send"


def test_classify_unknown_post_as_medium_risk() -> None:
    axiom.init(api_key="k", base_url="http://t")
    ix = HttpInterceptor("a", "learn", GovernanceRecorder("a"))
    assert ix._assess_risk("POST", "https://unknown.example/api", None) == "medium"


def test_classify_get_as_low_risk() -> None:
    axiom.init(api_key="k", base_url="http://t")
    ix = HttpInterceptor("a", "learn", GovernanceRecorder("a"))
    assert ix._assess_risk("GET", "https://unknown.example/x", None) == "low"


@responses.activate
def test_cost_limit_kills_agent(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="enforce", recorder=rec, max_cost=0.01)
    ix._total_cost = 1.0
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            dc.return_value.govern = MagicMock()
            dc.return_value.report = MagicMock()
            with pytest.raises(ConnectionError):
                requests.Session().get("https://httpbin.org/get")
    finally:
        ix.uninstall()


@responses.activate
def test_governance_api_failure_fails_open_in_learn(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="learn", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            dc.return_value.govern = MagicMock(side_effect=RuntimeError("api down"))
            dc.return_value.report = MagicMock()
            r = requests.Session().get("https://httpbin.org/get")
            assert r.status_code == 200
    finally:
        ix.uninstall()


@responses.activate
def test_governance_api_failure_fails_closed_in_enforce(base_url: str) -> None:
    responses.add(responses.GET, "https://httpbin.org/get", json={}, status=200)
    axiom.init(api_key="k", base_url=base_url)
    rec = GovernanceRecorder(agent_id="a")
    ix = HttpInterceptor(agent_id="a", mode="enforce", recorder=rec)
    ix.install()
    try:
        with patch("axiom.interceptor.default_client") as dc:
            dc.return_value.govern = MagicMock(side_effect=RuntimeError("api down"))
            dc.return_value.report = MagicMock()
            with pytest.raises(ConnectionError, match="unavailable"):
                requests.Session().get("https://httpbin.org/get")
    finally:
        ix.uninstall()
