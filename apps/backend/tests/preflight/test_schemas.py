"""Schema tests for /v1/preflight."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from axiom.schemas.preflight import PreflightRequest, PreflightResponse
from axiom.services.policy.evaluator import Verdict
from axiom.services.preflight.confidence import PreflightConfidence


def test_preflight_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PreflightRequest.model_validate(
            {
                "action": {"type": "x"},
                "agent_id": str(uuid4()),
                "extra": 1,
            }
        )


def test_preflight_response_serializes_to_json() -> None:
    r = PreflightResponse(
        prediction_id="pred_x",
        predicted_verdict=Verdict.APPROVE,
        rule_id="r1",
        policy_id="p",
        policy_version="1",
        reasoning="ok",
        explanation="exp",
        probably_definitive=True,
        confidence=PreflightConfidence.HIGH,
        cached=False,
        cache_age_seconds=None,
        correlation_id="c",
    )
    s = r.model_dump_json()
    data = json.loads(s)
    assert data["predicted_verdict"] == "approve"
    assert data["confidence"] == "high"


def test_preflight_response_includes_disclaimer() -> None:
    r = PreflightResponse(
        prediction_id="p",
        predicted_verdict=Verdict.DENY,
        rule_id=None,
        policy_id="pol",
        policy_version="1",
        reasoning="r",
        explanation="e",
        probably_definitive=True,
        confidence=PreflightConfidence.HIGH,
        cached=False,
        cache_age_seconds=None,
        correlation_id="c",
    )
    assert "cryptographic receipt" in r.disclaimer
    assert "POST /v1/govern" in r.disclaimer


def test_preflight_response_cache_age_none_when_not_cached() -> None:
    r = PreflightResponse(
        prediction_id="p",
        predicted_verdict=Verdict.APPROVE,
        rule_id=None,
        policy_id="pol",
        policy_version="1",
        reasoning="r",
        explanation="e",
        probably_definitive=True,
        confidence=PreflightConfidence.HIGH,
        cached=False,
        cache_age_seconds=None,
        correlation_id="c",
    )
    assert r.cache_age_seconds is None
