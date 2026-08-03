# Phase 1.6 Plan — Foundation Cleanup

## Baseline (reconnaissance — 2026-04-16)

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| HEAD commit | `171bdcb` (Phase 1.5) | `171bdcb` | ✅ |
| Working tree | clean | clean | ✅ |
| Global coverage (line) | ~81.5% | **81.47%** | ✅ |
| `services/auth.py` coverage | ~55% | **55%** (85 stmts missed of 191) | matches Phase 1.5 |
| `google_oauth.py` in report | excluded (ADR-020) | **not listed** (omitted) | ✅ |
| `pytest.ini_options` / addopts `cov-fail-under` | 80 | **80** (via `--cov-fail-under=80`) | ✅ |
| `[tool.coverage.run] branch` | false | **false** | ✅ |
| `omit` contains `google_oauth` | yes | `**/services/google_oauth.py` | ✅ |
| `.importlinter` at repo root | absent this phase | **absent** | expected |
| `pytest-httpx` in dev deps | likely no | **not present** | ✅ |
| Security tests | 49 | **49 collected** | ✅ |

**Uncovered lines in `axiom/services/auth.py` (from `--cov-report=term-missing`):**
29, 100–162, 175–177, 179–181, 183–184, 187, 200–201, 203, 211, 216, 219–222, 234–235, 237, 244–246, 259–320.

**`google_oauth.py`:** omitted from coverage; no line-level report until omit is removed.

**Per-file coverage convention (Phase 1.75+):** Clear default `addopts` so pytest-cov does not stack two `--cov` sources (which double-instruments and can break timing-sensitive tests):

```bash
cd apps/backend
uv run pytest --override-ini="addopts=" --cov=axiom.services.auth --cov-fail-under=95 tests/ -q
uv run pytest --override-ini="addopts=" --cov=axiom.services.google_oauth --cov-fail-under=90 tests/ -q
```

The same `--override-ini="addopts="` pattern is used in CI for the per-file gates.

---

## 3.1 Scope

Close Phase 1.5 deviations documented in ADR-019 / ADR-020. Do not expand scope (no new endpoints, migrations, prod deps, frontend, crypto).

---

## 3.2 Implementation order (strict)

1. Add `pytest-httpx` + `import-linter` to dev deps → `uv sync`
2. Add JWKS mock fixtures in `tests/fixtures/google_jwks.py` (session RSA keypair + `make_google_id_token` + `mock_google_jwks` via `httpx_mock`)
3. Write missing tests for `axiom.services.auth`: password-reset edge cases, refresh-token edge cases, lockout clear-on-success, bcrypt on nonexistent user, and any remaining lines from the missing report
4. Write missing tests for `axiom.services.google_oauth` using mocked JWKS (paths per Phase 1.6 spec: happy path, state, aud/iss, expiry, alg none, HS256, JWKS failure, unknown kid, no sub, email not verified)
5. Remove `axiom/services/google_oauth.py` from `[tool.coverage.run] omit`
6. Flip `[tool.coverage.run] branch = true`; align pytest global gate with `--cov-branch --cov-fail-under=80`
7. Run coverage; fix newly exposed branch gaps with targeted tests (or ≤2 codebase-wide `# pragma: no branch` with justification)
8. Add `.importlinter` at repo root: **models** forbidden-import contract + **layers** contract (crypto-leaf and pipeline-protocols forbidden contracts deferred until those packages exist — import-linter requires real modules as `source_modules`)
9. Add `import-linter` step to `.github/workflows/ci.yml` plus per-file coverage steps for `auth` ≥95% and `google_oauth` ≥90% (ensure env vars match DB/Redis/secrets)
10. Update `docs/decisions.md`: ADR-020 addendum (CLOSED); ADR-021 (import-linter)
11. Run full verification (Phase 1.6 §6)
12. Commit, push, tag `v0.1.6-cleanup` per handoff

---

## 3.3 Test gates

- `axiom.services.auth` ≥ **95%** (per-file)
- `axiom.services.google_oauth` ≥ **90%** (per-file)
- Global: **branch + line** gate ≥ **80%** with `--cov-branch`
- `uv run lint-imports --config ../../.importlinter` (from `apps/backend`) exits **0**
- Full suite and all **49** security tests pass with no regression

---

## 3.4 Known risks + mitigations

| Risk | Mitigation |
|------|------------|
| **Double `--cov` from `addopts` + CLI** skews timing / fails rate-limit tests | Use `--override-ini addopts='-ra -q --strict-markers'` (or narrow addopts) for per-file runs; document same pattern for local verification |
| **Branch coverage drops combined % below 80%** | Add focused branch tests; avoid lowering `fail_under` |
| **`import-linter` layers contract** fails on existing imports (routers → models, etc.) | Adjust only import sites (lazy imports, TYPE_CHECKING) within scope; if cycle needs redesign, stop and report |
| **JWKS module cache** in `google_oauth._jwks_cache` bleeds between tests | Clear cache in fixture teardown or module-level reset where needed |
| **`python-jose` vs `cryptography` token minting** mismatch | Match signing to `verify_google_id_token` (RS256, `kid` header) exactly as production code expects |
| **Pragma creep** | Cap `# pragma: no cover` / `# pragma: no branch` per Phase 1.6 limits; prefer real tests |

---

## Completion report

- Git revision: **`4d3e6c4`** on `main`, tag **`v0.1.6-cleanup`**
- Global coverage (branch+line): **~85.6%** combined (target ≥80%)
- `services/auth.py` coverage: **~99.2%** per-file gate (target ≥95%)
- `google_oauth.py` coverage: **100%** per-file gate (target ≥90%)
- New tests added: **~62** (new modules `test_auth_service_coverage.py`, `test_google_oauth_verify.py`, plus router OAuth cases in `test_auth_google.py`; total suite **136** tests)
- Branch gaps: global gate green with `branch = true` and `--cov-branch` in default `addopts`
- Import-linter contracts: **2** active (models + layers), all passing; crypto / pipeline contracts documented for Phase 1.75 in `.importlinter` and ADR-021

### What Phase 1.75 starts with

- Hardened foundation with coverage debt closed
- Architectural boundaries enforced by tooling
- Rollback anchor at `v0.1.6-cleanup`
- Clean mypy, ruff, pre-commit, CI
