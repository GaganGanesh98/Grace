"""Stage 1 (Intent): canonicalize the action + scan user-visible text for injection.

Responsibility: parse + validate. No policy lookups, no verdicts. Produces
``ctx.action_canonical`` (RFC 8785 bytes) and ``ctx.injection_matches``
(tuple of ``InjectionMatch``). Stage 3 (Authority) decides what to DO with a
match; Stage 1 only surfaces the signal.

Fail modes:
  * action is not JSON-canonicalizable (e.g. contains ``bytes``, NaN, cycles) ->
    ``StageResult(ok=False, error="action_not_canonicalizable")``. Runner
    short-circuits to DENY but still emits a receipt.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from axiom.services.crypto.canonical_json import NonCanonicalizableError, canonicalize
from axiom.services.pipeline.protocols import PipelineContext, StageResult
from axiom.services.prompt_injection.detector import InjectionDetector, InjectionMatch

_SCANNABLE_KEYS: frozenset[str] = frozenset(
    {"body", "text", "content", "message", "prompt", "subject", "description"}
)


def _iter_scannable_text(obj: object, *, max_depth: int = 6) -> Iterable[str]:
    """Yield text from fields that semantically hold user content.

    We deliberately ignore structural fields (ids, types, timestamps) to avoid
    false-positive injection matches on identifiers like ``"role_hijack_v1"``.
    """

    if max_depth <= 0:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key.lower() in _SCANNABLE_KEYS and isinstance(value, str):
                yield value
            else:
                yield from _iter_scannable_text(value, max_depth=max_depth - 1)
    elif isinstance(obj, list | tuple):
        for item in obj:
            yield from _iter_scannable_text(item, max_depth=max_depth - 1)


class IntentStage:
    """Canonicalize + scan-for-injection."""

    name = "intent"

    def __init__(self, detector: InjectionDetector | None = None) -> None:
        self._detector = detector or InjectionDetector()

    async def execute(self, ctx: PipelineContext) -> StageResult:
        start = time.monotonic()
        try:
            canonical = canonicalize(ctx.action)
        except (NonCanonicalizableError, TypeError) as exc:
            return StageResult(
                ok=False,
                stage_name=self.name,
                duration_ms=(time.monotonic() - start) * 1000,
                error=f"action_not_canonicalizable: {exc}",
            )

        ctx.action_canonical = canonical

        matches: list[InjectionMatch] = []
        for text in _iter_scannable_text(ctx.action):
            matches.extend(self._detector.scan(text))
        ctx.injection_matches = tuple(matches)

        return StageResult(
            ok=True,
            stage_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
            data={
                "canonical_bytes": len(canonical),
                "injection_matches": len(matches),
            },
        )
