"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def base_url() -> str:
    return "http://axiom.test"


@pytest.fixture
def api_headers() -> dict[str, str]:
    return {"Authorization": "Bearer axm_live_test", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _reset_axiom_config() -> None:
    from axiom.config import _reset_config_for_tests

    _reset_config_for_tests()
    yield
    _reset_config_for_tests()
