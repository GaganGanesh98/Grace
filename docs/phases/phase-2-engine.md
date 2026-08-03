# Phase 2 Plan — The Governance Engine

**Target tag:** `v0.2.0-engine`
**Prior anchor:** `v0.1.75-crypto` (commit `b84fdb1`)
**Positioning:** EvidenceOps for AI agents. `/v1/govern` is MATCH-GAAS. `/v1/verify` and `/v1/disclose` are WEDGES.

## 4.1 Scope

Wire Phase 1.75 primitives (`HybridSigner`, `PolicyEvaluator`, `InjectionDetector`, `MerkleTree`, `canonical_json`,
`AES-GCM`) into a 6-stage governance pipeline. Expose three public endpoints:

- `POST /v1/govern`        — API-key auth, 100/min/key — MATCH-GAAS
- `GET  /v1/verify/{id}`   — public, 60/min/IP        — WEDGE
- `POST /v1/disclose`      — API-key auth, 30/min/key — WEDGE

Plus: receipt/Merkle-append service, deterministic explanation engine, API-key verification service,
new Pydantic schemas, new import-linter contract, Hypothesis property tests, end-to-end tests,
latency benchmark, and a small Alembic migration that adds per-project Merkle columns + encrypted-evidence
columns to existing tables.

## 4.2 Deviations from prompt (flagged in reconnaissance)

| # | Prompt assumption | Reality | Chosen action |
|---|-------------------|---------|---------------|
| 1 | import-linter contract 3 = pipeline-protocols-pure | contract 3 = crypto-leaf (landed Phase 1.75) | add pipeline-protocols as **contract 4**; keep crypto-leaf as contract 3 |
| 2 | `merkle_nodes` is per-project | Phase 1.75 schema is global (no `project_id` column) | **add Alembic migration** adding `project_id` + composite PK `(project_id, leaf_index)` |
| 3 | receipts persist encrypted evidence | `receipts` has no evidence columns | same migration adds `evidence_nonce`, `evidence_ciphertext`, `evidence_key_id` |
| 4 | `services/api_key/` (new verification service) | existing `services/api_keys.py` is CRUD | create new package, leave CRUD alone |
| 5 | rate-limit key for govern/disclose | default slowapi is IP | add `api_key_limit_key` function that reads presented-key header |
| 6 | prefix `axiom_live_` | Phase 1 uses `axm_live_` | keep `axm_live_` (not WEDGE material, changing it would break existing keys) |

## 4.3 Implementation order (strict)

1. **Migration** — `alembic revision` adding `merkle_nodes.project_id` + evidence columns on `receipts`.
2. **Model updates** — `MerkleNode.project_id`; composite PK. `Receipt.evidence_nonce/ciphertext/key_id` nullable (old receipts won't have them; for Phase 2 they will always be populated).
3. **Pipeline contracts** — `services/pipeline/__init__.py`, `services/pipeline/protocols.py` (`Stage`, `StageResult`, `PipelineContext`, `PipelineMode`).
4. **Import-linter contract 4** — activate "pipeline-protocols-pure": `axiom.services.pipeline.protocols` must not import from `axiom.routers`, `axiom.middleware`, `axiom.models`, `axiom.db`.
5. **6 stages** — `services/pipeline/stages/{intent,strategy,authority,dispatch,evidence,receipt}.py`.
6. **Runner** — `services/pipeline/runner.py` with fail-closed orchestration + DENY short-circuit through Evidence+Receipt.
7. **Merkle append** — `services/receipt/merkle_append.py` with Postgres advisory lock keyed on project_id, simple full-rebuild, inclusion-proof generation.
8. **Receipt service** — `services/receipt/service.py` building evidence payload, signing, appending, persisting Execution+Receipt+MerkleNode atomically.
9. **Explanation engine** — `services/explanation/engine.py` template renderer.
10. **API-key verification** — `services/api_key/service.py` (`verify_key`, `APIKeyContext`, rate-limit accounting).
11. **Schemas** — `schemas/governance.py` with strict `extra="forbid"` Pydantic models.
12. **Routers** — `routers/govern.py`, `routers/verify.py`, `routers/disclose.py`.
13. **Wire into main.py** — include routers, register rate-limit key functions.
14. **Signer keys in settings** — add `axiom_ed25519_private_pem`, `axiom_ed25519_public_pem`, `axiom_ml_dsa_private`, `axiom_ml_dsa_public`, `axiom_evidence_key` to `Settings` (all SecretStr / base64). Add a `get_hybrid_signer_keys()` helper that loads them (generates once on startup if missing in dev).
15. **Tests** — unit tests per module; e2e smoke; property tests; latency benchmark.
16. **Verification** — Section 7 gauntlet.
17. **Adversarial review** — Section 8 10/10.
18. **Commit + tag `v0.2.0-engine`.**

## 4.4 Gates

| Gate | Where | Target |
|------|-------|--------|
| Branch coverage global | `pytest --cov=axiom --cov-branch` | ≥ 80 % |
| Pipeline module | `cov=axiom.services.pipeline` | ≥ 95 % |
| Receipt module | `cov=axiom.services.receipt` | ≥ 95 % |
| Explanation module | `cov=axiom.services.explanation` | ≥ 90 % |
| API-key module | `cov=axiom.services.api_key` | ≥ 95 % |
| Router — govern | `cov=axiom.routers.govern` | ≥ 90 % |
| Router — verify | `cov=axiom.routers.verify` | ≥ 90 % |
| Router — disclose | `cov=axiom.routers.disclose` | ≥ 90 % |
| Existing 1.6/1.75 per-module gates | unchanged | preserved |
| `lint-imports` | contract 4 active | pass |
| `mypy src` | strict | clean |
| `ruff check + format --check` | — | clean |
| `/v1/govern` P95 latency | local | < 250 ms |
| Hypothesis properties | fail-closed + merkle round-trip | pass |
| e2e `/v1/govern → /v1/verify → /v1/disclose` | — | pass |
| No V1 references | `grep axiom-control-center|axiom-v1` | zero |

## 4.5 Known risks + mitigations

- **Merkle concurrent-append race** — two `/v1/govern` for same project could race on leaf_index. Mitigation: `pg_advisory_xact_lock(hashtext('axiom:merkle:' || project_id))` inside the same DB transaction; `SELECT COALESCE(MAX(leaf_index), -1)+1 FROM merkle_nodes WHERE project_id=:p` after acquiring.
- **`/v1/verify` DoS** — public endpoint. Mitigation: slowapi `60/min/IP` via existing Redis-backed limiter + response-size cap (single receipt only).
- **`/v1/disclose` cross-project leak** — Mitigation: API-key verification returns `project_id`; all disclose queries are `WHERE executions.project_id = :api_key.project_id`. Test asserts zero cross-project.
- **Pipeline exception masks bug** — Fail-closed writes DENY receipt but devs need visibility. Mitigation: `logger.error("pipeline_stage_exception", exc_info=True, correlation_id=…)`.
- **Merkle rebuild cost at N=10k** — O(n) per append. Mitigation: Phase 2 accepts it (sub-100 ms locally until ~50 k leaves); Phase 5 adds cached subroots. Latency test pins N<1k.
- **PII in logs** — action payload may contain PII. Mitigation: never log `ctx.action` at INFO; only `correlation_id`, `verdict`, `policy_id`, `leaf_index`.
- **Single global signer key** — per-project keys land in Phase 2.5. Mitigation: the single-key helper is explicitly "phase-2 only" with a TODO pointer.
- **Missing policy / no agent / invalid action.type** — Stage 2 sets `policy_id=None`; Stage 3 defaults to DENY with `reasoning="no policy configured"`. Test covered.

## 4.6 MATCH vs WEDGE tagging (engineering priority)

- 🔥 **WEDGE files** get the polish budget (extra docs, schema clarity, more tests, error messages as sales copy): `routers/verify.py`, `routers/disclose.py`, `services/receipt/*`, `services/explanation/engine.py`, `schemas/governance.py` (verify+disclose response models).
- 🎯 **MATCH-GAAS files** meet spec and move on: `routers/govern.py`, `services/pipeline/stages/{intent,strategy,authority,dispatch}.py`, `services/api_key/service.py`.

## 4.7 Out of scope (explicit list)

Everything in Section 0's "NOT included" list: frontend, PDF export, public verify page (UI), policy templates, policy change accountability, compliance packs, bitcoin anchoring, regulator portal, replay/compare, intelligent PI defense, V1 code access, per-project keys (Phase 2.5), LLM explanations (Phase 3.5+).

## 4.8 Dependencies

**Zero new production dependencies.** Zero new dev dependencies. Everything below already in lockfile:
- fastapi, sqlalchemy[asyncio], asyncpg, pydantic, slowapi, rfc8785, dilithium-py, cryptography, structlog,
  redis, pytest, pytest-asyncio, hypothesis, import-linter.

## 4.9 Success criteria (copy-paste verification from Section 7 of the prompt)

Running the Section 7 command block end-to-end produces zero failures. Section 8 produces 10/10. `git diff HEAD`
shows no changes to `services/crypto/*` (locked). `grep -r "V1\|axiom-control-center\|axiom-v1"` on new files and
the plan doc returns nothing.

---

## Completion report

- Prep commit: `9949587 chore(phase-2-prep): migration + plan + tooling for v0.2.0-engine`
- Engine commit: `96a3719 feat(phase-2): governance engine — /v1/govern + /v1/verify + /v1/disclose`
- Tag: `v0.2.0-engine` (applied on `96a3719`)

### Deliverables

| Category | Count |
|---|---|
| Alembic migrations | 1 |
| Models touched | 2 (MerkleNode, Receipt) |
| New services (packages) | 4 (pipeline, receipt, explanation, api_key) |
| Pipeline stages | 6 |
| Routers | 3 (govern, verify, disclose) |
| Pydantic schemas | 1 file, 8 models |
| Import-linter contracts | +1 (pipeline-protocols-pure) |
| Test files | 18 |
| Test cases added | 129 |

### Coverage gates (final)

| Scope | Gate | Actual |
|---|---|---|
| global (branch) | ≥ 80 % | 94.08 % |
| services.pipeline | ≥ 95 % | 98.07 % |
| services.receipt | ≥ 95 % | 96.97 % |
| services.explanation | ≥ 90 % | 97.14 % |
| services.api_key | ≥ 95 % | 96.88 % |
| routers.govern | ≥ 90 % | 95.35 % |
| routers.verify | ≥ 90 % | 100 % |
| routers.disclose | ≥ 90 % | 92.13 % |
| (existing) services.auth | ≥ 95 % | 100 % |
| (existing) services.google_oauth | ≥ 90 % | 100 % |
| (existing) services.crypto | ≥ 95 % | 96.27 % |
| (existing) services.policy | ≥ 90 % | 100 % |
| (existing) services.prompt_injection | ≥ 95 % | 100 % |

### Latency

- `/v1/govern` P50 = 91.6 ms, P95 = 122.4 ms, P99 = 260.6 ms. Budget 250 ms met at P95.
- Skipped under coverage instrumentation (tracer overhead); run with `--no-cov tests/e2e/test_latency.py`.

### Adversarial review: 10/10 passed

See `tests/security/test_phase_2_adversarial.py` for the 10 persistent invariants:
fail-closed on Strategy error, Merkle concurrency integrity, cross-project disclosure scope,
constant-time key compare, PI detection under Unicode obfuscation, no evidence leak in
`/v1/verify`, explanation integrity, replay produces distinct receipts, rate-limit keyed on
API key (not UA), and biological-metaphor grep.

### MATCH-GAAS shipped (4)

`POST /v1/govern`, 6-stage pipeline, policy evaluation with 4 verdicts, shadow + enforce
modes. 4 regex PI categories (partial — the full intelligent PI layer lands in Phase 3.5).

### WEDGE shipped (5)

Merkle tree with inclusion proofs, Ed25519 + ML-DSA-65 hybrid signatures,
**`GET /v1/verify` public no-auth**, **`POST /v1/disclose` selective disclosure with
per-receipt proofs**, explanation with legal citations. Plus: AES-256-GCM encrypted
evidence; offline-verifiable receipts (50-line Python script using the public keys surfaced
by `/v1/verify`).

## What Phase 2.5 starts with

- Working `/v1/govern` that returns signed receipts (Ed25519 + ML-DSA-65).
- Working `/v1/verify` that anyone can call — public receipt verification is live.
- Working `/v1/disclose` for GDPR / subpoena compliance with per-receipt Merkle proofs
  and AES-GCM decryption.
- Single AXIOM-wide evidence key + single hybrid signer keypair (auto-generated in
  dev/test; env-pinned in prod).
- Deterministic explanation engine shipping legal citations + remediation guidance.
- Fail-closed runner that ensures every request emits a receipt (no silent drops).
- Postgres advisory-lock-based per-project Merkle append.
- 380 passing tests (10 are persistent adversarial invariants).

## What Phase 2.5 adds

- Per-project Ed25519 + ML-DSA-65 signing keypairs.
- Per-project AES-256-GCM evidence keys.
- Key rotation flow (new key, old key kept for verification of historical receipts).
- Key fingerprint surfaced in receipt envelope and `/v1/verify` response.
- Migration of existing Phase-2 receipts to a "default project key" cohort.
