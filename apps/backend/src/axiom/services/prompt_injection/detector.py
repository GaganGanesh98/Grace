"""Regex-based prompt injection detection (four categories)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class InjectionCategory(StrEnum):
    INSTRUCTION_OVERRIDE = "instruction_override"
    SYSTEM_PROMPT_LEAK = "system_prompt_leak"
    ROLE_HIJACK = "role_hijack"
    OUTPUT_FORMAT_ABUSE = "output_format_abuse"


@dataclass(frozen=True)
class InjectionMatch:
    category: InjectionCategory
    pattern_id: str
    matched_span: tuple[int, int]
    matched_text: str


_PATTERN_DEFS: tuple[tuple[InjectionCategory, str, str], ...] = (
    (
        InjectionCategory.INSTRUCTION_OVERRIDE,
        "instruction_override_v1",
        r"(?is)\b(?:"
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?"
        r"|disregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|rules?|guidelines?)"
        r"|forget\s+(?:the\s+)?(?:rules?|instructions?|constraints?|guidelines?)"
        r"|override\s+(?:the\s+)?(?:system|developer)\s+message"
        r"|(?:start\s+)?a\s+new\s+session\s+(?:with|where)\s+no\s+rules"
        r")\b",
    ),
    (
        InjectionCategory.SYSTEM_PROMPT_LEAK,
        "system_prompt_leak_v1",
        r"(?is)\b(?:"
        r"repeat\s+(?:your\s+)?(?:system|hidden|initial)\s+prompt"
        r"|what\s+(?:are|is)\s+your\s+(?:system\s+)?instructions?"
        r"|print\s+(?:your\s+)?(?:system\s+)?prompt"
        r"|show\s+(?:me\s+)?(?:the\s+)?(?:full\s+)?(?:system\s+)?(?:message|prompt)"
        r"|reveal\s+(?:your\s+)?(?:developer|system)\s+message"
        r")\b",
    ),
    (
        InjectionCategory.ROLE_HIJACK,
        "role_hijack_v1",
        r"(?is)\b(?:"
        r"you\s+are\s+now\s+(?:a\s+)?[\w\-\s]{1,40}"
        r"|from\s+now\s+on,?\s+act\s+as\s+[\w\-\s]{1,40}"
        r"|pretend\s+(?:to\s+be|you\s+are)\s+[\w\-\s]{1,40}"
        r"|(?:assume|adopt)\s+(?:the\s+)?role\s+of\s+[\w\-\s]{1,40}"
        r")\b",
    ),
    (
        InjectionCategory.OUTPUT_FORMAT_ABUSE,
        "output_format_abuse_v1",
        r"(?is)(?:"
        r"[\u200b\u200c\u200d\u2060\ufeff]"
        r"|```\s*\{"
        r"|```\s*<"
        r"|<\s*script[\s>]"
        r")",
    ),
)


class InjectionDetector:
    """Loads four case-insensitive patterns (one per category)."""

    def __init__(self) -> None:
        self._patterns: tuple[tuple[InjectionCategory, str, re.Pattern[str]], ...] = tuple(
            (cat, pid, re.compile(pat)) for cat, pid, pat in _PATTERN_DEFS
        )

    def scan(self, text: str) -> tuple[InjectionMatch, ...]:
        """Return all matches; empty tuple means no suspicious patterns."""
        text = unicodedata.normalize("NFKC", text)
        matches: list[InjectionMatch] = []
        for category, pattern_id, compiled in self._patterns:
            for m in compiled.finditer(text):
                matches.append(
                    InjectionMatch(
                        category=category,
                        pattern_id=pattern_id,
                        matched_span=(m.start(), m.end()),
                        matched_text=m.group(0),
                    )
                )
        return tuple(matches)

    def is_suspicious(self, text: str) -> bool:
        return len(self.scan(text)) > 0


def normalize_for_scan(
    text: str,
    form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFKC",
) -> str:
    """Normalize Unicode for scanning (explicit helper for tests)."""
    return unicodedata.normalize(form, text)
