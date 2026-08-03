from __future__ import annotations

import logging
from typing import Any

import structlog

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "token",
        "secret",
        "key_hash",
        "authorization",
        "api_key",
        "jwt",
        "refresh_token",
        "access_token",
    }
)


def redact_sensitive(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict):
        if str(key).lower() in SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_structlog(*, log_level: str, environment: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(level=level)
    is_prod = environment.lower() == "production"
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_sensitive,
    ]
    if is_prod:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.processors.StackInfoRenderer())
        processors.append(structlog.dev.ConsoleRenderer(colors=False))
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
