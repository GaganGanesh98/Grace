"""Confidence labeling for pre-flight predictions.

Three labels:
- HIGH: cache miss (fresh computation) + rule is deterministic (no context-dependent operators)
- MEDIUM: cache hit with age < 30min OR cache miss with context-dependent rule
- LOW: cache hit with age >= 30min or context-dependent cached path with age >= 30min

Context-dependent operators (from Phase 1.75 policy evaluator):
- gt / lt applied to time-based fields (e.g., "request_hour")
- gt / lt applied to rate-limited fields (e.g., "requests_this_hour")

Phase 2.25 conservatively treats ANY gt/lt operator in the matched rule as
context-dependent, since Phase 1.75's evaluator does not distinguish timestamp
vs static comparisons. Phase 3.85 (replay/compare) refines this.
"""

from __future__ import annotations

from enum import StrEnum

from axiom.services.policy.evaluator import PolicyRule


class PreflightConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_CONTEXT_DEPENDENT_OPERATORS = {"gt", "lt"}


def is_rule_deterministic(rule: PolicyRule | None) -> bool:
    """Returns True iff the rule's predicate uses only deterministic operators.

    None (default verdict hit) is considered deterministic.
    """
    if rule is None:
        return True

    def _scan(node: dict[str, object]) -> bool:
        for value in node.values():
            if isinstance(value, dict):
                op = value.get("op")
                if op in _CONTEXT_DEPENDENT_OPERATORS:
                    return False
                if not _scan(value):
                    return False
        return True

    return _scan(rule.when)


def compute_confidence(
    *,
    cache_hit: bool,
    cache_age_seconds: int,
    rule_is_deterministic: bool,
) -> PreflightConfidence:
    """Pure function. No I/O."""
    if cache_hit:
        if cache_age_seconds >= 1800:  # 30 min
            return PreflightConfidence.LOW
        # Cached predictions are never HIGH — staleness vs live govern always possible.
        return PreflightConfidence.MEDIUM
    # Cache miss (fresh computation)
    if not rule_is_deterministic:
        return PreflightConfidence.MEDIUM
    return PreflightConfidence.HIGH
