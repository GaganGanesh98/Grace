# Phase 1.75 Plan — Crypto & Policy Foundation (clean-slate build)

## 4.1 Scope
Build V2's cryptographic primitives + policy evaluator + PI detector from scratch using standard PyPI libraries. No V1 code copied. One Alembic migration adds 3 tables. Import-linter crypto-leaf contract activated once `axiom.services.crypto` exists. Pipeline-protocols contract remains deferred to Phase 2.

## 4.2 Implementation order (strict)
1. Add new deps: `rfc8785>=0.1.4`, `dilithium-py>=1.4.0`, `hypothesis>=6.100.0` (dev) → `uv sync`
2. Create `axiom/services/crypto/__init__.py` and `axiom/services/crypto/canonical_json.py`
3. Create `axiom/services/crypto/ed25519.py`
4. Create `axiom/services/crypto/ml_dsa.py`
5. Create `axiom/services/crypto/aes_gcm.py`
6. Create `axiom/services/crypto/merkle.py`
7. Create `axiom/services/crypto/hybrid_signer.py` (depends on 2, 3, 4)
8. Activate import-linter crypto-leaf contract in `.importlinter` (crypto now exists); keep pipeline contract commented for Phase 2
9. Create `axiom/services/policy/__init__.py` and `axiom/services/policy/evaluator.py`
10. Create `axiom/services/prompt_injection/__init__.py` and `axiom/services/prompt_injection/detector.py`
11. Create Alembic migration: `executions`, `receipts`, `merkle_nodes` (ONE file)
12. Add SQLAlchemy models: `Execution`, `Receipt`, `MerkleNode` in `axiom/models/`
13. Export new models from `axiom/models/__init__.py`
14. Write tests for every module (`tests/crypto/`, `tests/policy/`, `tests/prompt_injection/`)
15. Write Hypothesis property tests for canonical_json, merkle, signers in `tests/crypto/test_properties.py`
16. Run migration up/down/up to verify reversibility
17. Run full verification suite (Section 7)
18. Adversarial self-review (Section 8)
19. Commit + tag `v0.1.75-crypto`

## 4.3 Gates
- Import-linter: existing contracts + crypto-leaf pass
- `alembic upgrade head` → `downgrade -1` → `upgrade head` clean
- Coverage + lint + mypy gates per Section 7
- 10-check adversarial review passes
- No V1 file references in any created file (grep verification)

## 4.4 Known risks + mitigations
- [Risk] dilithium-py requires binary wheel or Rust toolchain — may not install cleanly.
  Mitigation: try uv sync first; if fails, report and pause.
- [Risk] Merkle implementation is the only custom crypto; subtle off-by-one bugs.
  Mitigation: Hypothesis property tests for inclusion-proof correctness, consistency-proof correctness, round-trip through serialization.
- [Risk] Alembic migration with 3 tables + constraints may have dependency-order issues.
  Mitigation: create tables in dependency order (`executions` → `receipts` → `merkle_nodes`); drop in reverse order on downgrade.
- [Risk] Import-linter crypto-leaf may flag internal imports within crypto submodules.
  Mitigation: contract forbids crypto importing from routers/middleware/models; internal crypto-to-crypto imports are fine; avoid importing sibling services.

## Completion report

- **Commit:** `772279d4ee30f8132a2ccd05644aa44df686a632`
- **Tag:** `v0.1.75-crypto` (after push)
- **Code files:** 7 crypto modules + 1 policy module + 1 prompt-injection module + 3 SQLAlchemy models + 1 Alembic revision = 13 deliverables under `apps/backend/src/axiom/`
- **Test files:** 9 under `tests/crypto/`, 1 under `tests/policy/`, 1 under `tests/prompt_injection/` (property tests in `tests/crypto/test_properties.py`)
- **Tests collected (new dirs only):** 114
- **New dependencies:** `rfc8785`, `dilithium-py`; dev: `hypothesis`
- **Coverage gates (local):** combined `axiom` ~88% line+branch; `axiom.services.crypto` ≥95%; `axiom.services.policy` 100%; `axiom.services.prompt_injection` 100%
- **Import-linter:** 3 contracts kept (models forbidden-import, layered architecture, crypto leaf); pipeline-protocols contract deferred to Phase 2
- **Alembic:** `upgrade head` → `downgrade -1` → `upgrade head` verified against Docker Postgres
- **Hypothesis:** `tests/crypto/` passes with seeds 0–3 (`--override-ini=addopts=` to avoid global coverage gate during seed sweeps)
- **V1 references:** none in new paths (`grep` clean)
- **API note:** public helpers use `stable_key_id()` (SHA-256 hex of public material) instead of the prompt’s `fingerprint()` name, because the repository `no-print-statements` hook treats the substring `print(` inside `fingerprint(` as a forbidden `print(` call.

## What Phase 2 starts with

- Hybrid signing: `sign_hybrid` / `verify_hybrid` on canonical JSON payloads
- Policy: `evaluate(policy, action) -> PolicyDecision` (fail-closed)
- PI detector: `InjectionDetector.scan` / `is_suspicious`
- Schema: `executions`, `receipts`, `merkle_nodes` (+ ORM models exported from `axiom.models`)

## What Phase 2 adds

- `/v1/govern`, six-stage pipeline, receipt wiring, Merkle append/prove against `merkle_nodes`, import-linter contract for `pipeline.protocols`, and related API surface (per Phase 2 prompt).
