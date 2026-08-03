"""Global SDK configuration (API base URL, timeout)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ._version import __version__

_LOG = logging.getLogger("axiom.sdk")


@dataclass
class _Config:
    api_key: str = ""
    base_url: str = "https://api.axiom.dev"
    timeout: float = 30.0
    debug: bool = False


_global_config = _Config()


def _reset_config_for_tests() -> None:
    """Reset process-wide config (tests only). Not part of the public API."""
    global _global_config
    _global_config = _Config()


def configure(
    api_key: str,
    base_url: str = "https://api.axiom.dev",
    timeout: float = 30.0,
) -> None:
    global _global_config
    _global_config = _Config(api_key=api_key, base_url=base_url, timeout=timeout, debug=False)


def get_config() -> _Config:
    if not _global_config.api_key:
        raise RuntimeError("axiom.init() must be called before using the SDK")
    return _global_config


def set_debug(enabled: bool) -> None:
    """Enable or disable debug logging for the ``axiom`` logger namespace.

    API keys are never written to logs, even when debug is enabled.
    """
    global _global_config
    _global_config.debug = enabled
    level = logging.DEBUG if enabled else logging.WARNING
    logging.getLogger("axiom").setLevel(level)
    _LOG.debug("axiom-sdk debug logging %s", "enabled" if enabled else "disabled")


def user_agent() -> str:
    return f"axiom-sdk-python/{__version__}"
