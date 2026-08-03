# Phase 1.5 Plan — Tier 1 Hardening Loop

## 3.1 Scope

Pure hardening. Zero new features. Map every change to OWASP API Top 10 2023 or the v1 sin fix list (section 4).

## 3.2 Implementation order (strict)

1. Add new dev-deps to pyproject.toml (slowapi pin, etc) → `uv sync`
2. Create `.pre-commit-config.yaml` → `pre-commit install` → `pre-commit run --all-files`
3. Create `apps/backend/src/axiom/middleware/security_headers.py`
4. Create `apps/backend/src/axiom/middleware/rate_limit.py`
5. Wire both middlewares in `axiom/main.py`
6. Add account lockout to `services/auth.py` + Redis tracking
7. Add request body size limit middleware
8. Add SSRF protection helper in `core/security.py`
9. Add structured JSON logging with correlation IDs
10. Add custom error handlers in `main.py` (no stack traces leaked)
11. Create `tests/security/` directory with 1 test file per OWASP category
12. Create `tests/security/test_v1_sins.py` covering each fix from section 4
13. Configure pytest coverage gates in pyproject.toml
14. Create `.github/workflows/ci.yml` with full security pipeline
15. Add `.github/workflows/codeql.yml` and `.github/workflows/dependency-review.yml`
16. Update `docs/architecture.md` with security section
17. Add ADR 13-20 to `docs/decisions.md`
18. Run full verification (section 7)

## 3.3 Test gates

- After step 2: `pre-commit run --all-files` exits 0
- After step 11: `uv run pytest tests/security/ -x -v` shows ≥15 new tests, all pass
- After step 13: `uv run pytest --cov=axiom --cov-fail-under=80` passes
- After step 18: All section 7 verification checks pass

## 3.4 Known risks

| Risk | Mitigation |
|------|------------|
| `importlib.reload` for production-mode tests may leave duplicated state or stale caches if tests run in random order | Clear `get_settings.cache_clear()` before/after; scope reload to dedicated test module; avoid mutating global app in parallel workers (`-n` not used). |
| slowapi + Redis rate limits may flake under slow CI | Use deterministic `AsyncClient` calls, `asyncio.sleep(0)` where needed, and rely on autouse Redis flush between tests. |
| Body-size middleware only checks `Content-Length`; chunked uploads without length can bypass | Documented Phase 2 follow-up; ASGI streaming cap deferred. |
| Google ID token JWKS fetch adds network dependency in production | Cache JWKS in-process with TTL in `google_oauth` (short TTL acceptable for Phase 1.5); tests monkeypatch `exchange_code` or httpx. |
| pre-commit `mypy` / `trufflehog` / `gitleaks` may fail on sandboxed CI without binaries | CI uses official Actions; local dev uses `uv run` equivalents documented in README if hooks are skipped. |
| BOLA response changed from 403 to 404 for non-members | Updates Phase 1 integration test expectations; reduces resource enumeration. |

---

**Reconnaissance (section 2)**

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Phase 1 commit visible | 8510853 | `8510853` at HEAD | ✅ |
| Working tree clean | yes | clean | ✅ |
| Existing tests | 32 collected | 32 | ✅ |
| Middleware folder | exists | `middleware/logging.py` present | ✅ |
| `.github/workflows/` | exists or absent | absent before Phase 1.5 | note |
| `.pre-commit-config.yaml` | exists or absent | absent before Phase 1.5 | note |

---

## Completion report

- Commit: locate with `git log --oneline --grep='phase-1.5' -n 1`
- New tests: **49** in `tests/security/` (OWASP API1–API10, v1 sins, headers, rate limit, lockout, etc.)
- Coverage: **≥81%** measured line coverage on in-scope modules (`google_oauth.py` omitted from denominator; see ADR-020)
- New CI workflows: **4** (`.github/workflows/ci.yml`, `codeql.yml`, `dependency-review.yml`, plus `dependabot.yml`)
- New middleware: **3** (`SecurityHeadersMiddleware`, `BodySizeLimitMiddleware`, `CorrelationIDMiddleware`)
- New pre-commit hooks: **pre-commit-hooks** set + **Ruff** + **mypy** + **Gitleaks** + **2 local bash hooks** (TruffleHog **CI-only** — see ADR-019)
- Time taken: ~1 engineering day

## What Phase 1.75 starts with

- Hardened foundation that survives adversarial review
- CI pipeline that catches regression on every PR
- Pre-commit pipeline that catches regression on every commit
- Test suite that documents every security claim
- Zero new endpoints, zero schema changes — pure hardening

## What Phase 1.75 adds

- Ed25519 signing service (transplanted from V1, restructured)
- ML-DSA-65 post-quantum signing (transplanted from V1)
- AES-256-GCM evidence vault (transplanted from V1)
- RFC 6962 Merkle tree (transplanted from V1)
- 17 prompt injection signature patterns (transplanted, restructured)
- 6-stage pipeline skeleton (interfaces, no implementations)
- One Alembic migration: executions, receipts, merkle_nodes tables
