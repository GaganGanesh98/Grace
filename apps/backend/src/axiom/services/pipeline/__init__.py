"""Six-stage governance pipeline (fail-closed orchestrator + stages).

Phase 2: Intent -> Strategy -> Authority -> Dispatch -> Evidence -> Receipt.
Each stage is a pure Protocol conformer; the runner enforces ordering, timing,
and fail-closed semantics (any exception coerces verdict=DENY while still
producing an evidence + receipt trail).
"""
