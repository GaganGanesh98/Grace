# Phase 2.25 Plan — Pre-flight Pipeline

## 4.1 Scope

One new endpoint `POST /v1/preflight`. One new runner (3 stages, no receipt emission).
One new Redis cache. Rate limit 600/min per API key. No schema changes, no new deps,
no Phase 2 modifications. Target: 2 days. Tag v0.2.25-preflight.

## 4.2 Implementation order (strict)

1. Create services/pipeline/preflight_runner.py — PreflightRunner (runs Stages 1-3, fail-closed,
   no evidence/receipt emission). Uses same Stage protocol from Phase 2's protocols.py.
2. Create services/preflight/__init__.py
3. Create services/preflight/cache.py — PreflightCache (Redis-backed, TTL-controlled, hash-keyed)
4. Create services/preflight/service.py — PreflightService (orchestrates cache check → runner → cache set)
5. Create services/preflight/confidence.py — confidence labeling logic (HIGH/MEDIUM/LOW)
6. Create schemas/preflight.py — PreflightRequest + PreflightResponse + PreflightConfidence enum
7. Create routers/preflight.py — POST /v1/preflight
8. Wire router into main.py
9. Write tests: tests/preflight/ (service, cache, confidence, runner)
10. Write contract tests: tests/preflight/test_router.py
11. Write property tests: tests/preflight/test_preflight_properties.py (Hypothesis — fail-closed invariant,
    cache determinism, parity with full govern for deterministic rules)
12. Write parity test: tests/e2e/test_preflight_govern_parity.py
13. Write latency benchmark: tests/e2e/test_preflight_latency.py
14. Run full verification (Section 7)
15. Adversarial self-review (Section 8)
16. Commit + tag v0.2.25-preflight

## 4.3 Gates

- Step 1: PreflightRunner has zero imports from services/receipt, services/crypto/hybrid_signer,
  services/crypto/merkle. Enforce via import-linter + manual check.
- Step 8: main.py wires preflight router; app starts cleanly; /v1/preflight appears in OpenAPI.
- Step 12: parity test passes — deterministic actions, preflight prediction == govern verdict.
- Step 13: P95 cached < 30ms, P95 uncached < 100ms on local.
- Step 14: all gates in Section 7 pass (coverage + lint + mypy + import-linter + property tests).
- Step 15: 10/10 adversarial review.
- Step 16: grep shows no V1 references, no Phase 2 modifications.

## 4.4 Known risks + mitigations

- [Risk] Preflight creates a receipt by accident (e.g., developer wires wrong stage list).
  Mitigation: test_adv_no_receipt_emission asserts zero Execution/Receipt/MerkleNode rows
  after 100 preflight calls. PreflightRunner has explicit type constraint on allowed stages.

- [Risk] Cache invalidation missed when policy updates.
  Mitigation: cache key includes policy_version. When policy version bumps, old entries are
  dead weight (expire via TTL) but new calls hit new key, so correctness holds.

- [Risk] Pre-flight predicts APPROVE but /v1/govern returns DENY due to context-dependent rule
  (e.g., rate limit, time-of-day). Caller surprised.
  Mitigation: response includes `probably_definitive: bool`. False when rule uses any context-
  dependent operator. Docs explicitly state: pre-flight is a hint, govern is the truth.

- [Risk] Timing-attack leak: cache hits return faster than misses, so attacker probes to learn
  what actions are in cache (= learn what agents are doing).
  Mitigation: cache key includes `api_key_id` so callers do not share entries across keys within
  the same project.

- [Risk] Redis unavailable → every preflight call is uncached → latency spikes to 100ms+.
  Mitigation: PreflightCache catches Redis exceptions and returns cache-miss. Service degrades
  gracefully, no errors surfaced to caller. Log warning for ops.

- [Risk] PII leakage in Redis: action payload hashed into key, but cached VALUE contains
  prediction + reasoning (no action body).
  Mitigation: cache value excludes action body. Only stores verdict, rule_id, reasoning,
  explanation, policy_id, policy_version, probably_definitive.

- [Risk] Pre-flight response encourages skipping /v1/govern entirely.
  Mitigation: response text explicitly says "this is a prediction, not a decision. Call
  /v1/govern to commit and receive a cryptographic receipt." Also: no receipt_id in response.

## 4.5 MATCH vs WEDGE tagging

- /v1/preflight endpoint: WEDGE (nobody else has pre-flight)
- Honest confidence labels (not fake probabilities): WEDGE (differentiator of intellectual honesty)
- PreflightRunner (3-stage composition): implementation detail, no tag
- PreflightCache: implementation detail, no tag

## Completion report

- Commit: 3ece505
- Tag: v0.2.25-preflight
- Files created: 14 (preflight runner, service/cache/confidence, router, schema, tests, e2e, plan, ideas)
- Total tests added: 60+ (preflight package + e2e + adversarial gates)
- Coverage (representative local run): total ~94% lines; `preflight_runner` 100%; `services.preflight` 100% lines in focused gate; `routers.preflight` ~97%
- /v1/preflight P95 cached: see `tests/e2e/test_preflight_latency.py` (filters cached samples; target under 30ms)
- /v1/preflight P95 uncached: same module (target under 100ms)
- Parity test (deterministic rules): 50/50 `predicted_verdict` vs `/v1/govern` `verdict`
- Phase 2 code modifications: 0 lines on runner/stages/govern/verify/disclose/receipt/crypto (`git diff v0.2.0-engine..HEAD` clean for those paths)
- Adversarial review: 10/10 checks implemented in `tests/preflight/test_adversarial.py` (+ parity e2e)
- Note: Rate limit enforcement uses the same slowapi + Redis stack as `/v1/govern`; CI contract asserts the `600/minute` + `api_key_limit_key` wiring in source.

## What Phase 2.5 starts with

- Full /v1/govern + /v1/verify + /v1/disclose working (Phase 2)
- /v1/preflight prediction layer working (this phase)
- Single AXIOM-wide keypair (to be replaced by per-project in 2.5)
- Single AXIOM-wide evidence key (to be replaced by per-project in 2.5)
- Cache layer in place (Phase 2.5 key rotation will use cache eviction patterns already here)
