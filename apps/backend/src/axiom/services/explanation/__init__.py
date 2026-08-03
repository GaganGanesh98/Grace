"""Deterministic, template-based explanation renderer.

Phase 2 intentionally stops at string composition. LLM-driven explanations
(with guardrails + token budget + fact-check) land in Phase 3.5+.
"""

from axiom.services.explanation.engine import ExplanationEngine

__all__ = ["ExplanationEngine"]
