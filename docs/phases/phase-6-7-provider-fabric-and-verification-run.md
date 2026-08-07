# Phase 6.7 — Provider Fabric closeout + Phase 7.0 verification run

**Status:** Ready to dispatch
**Branch:** `feat/provider-fabric-closeout`
**Context:** Most of Phase 6.7 already landed (see below). This closes the one
remaining item and runs the gates Phase 7.0 could not.

---

## Part 0 — Run the Phase 7.0 gates (do this first, it may generate work)

Phase 7.0 (`feat/mcp-governance-server`) was written and statically verified —
ruff, ruff-format, mypy `--strict`, and all five import-linter contracts pass —
but **the test suite was never executed** because the authoring environment had
no Postgres/Redis. Roughly 35 new tests in `apps/backend/tests/mcp/` are
unproven.

```bash
./axiom dev          # Postgres 18 on :5433, Redis on :6380
cd apps/backend && uv sync      # picks up the new `mcp>=2.0.0` dependency
uv run pytest tests/mcp/ -v
./axiom test                    # full gate parity with CI
```

Expect friction in these specific places, and fix what you find rather than
loosening the assertions:

1. **`mcp>=2.0.0` must actually resolve.** The SDK renamed `FastMCP` →
   `MCPServer` (`mcp.server.mcpserver`) in 2.0. If `uv sync` pulls something
   older, the import in `axiom/mcp/server.py` fails outright.
2. **The `/mcp` mount needs the session manager running.** `main.py`'s lifespan
   enters `session_manager_lifespan()` when `app.state.mcp_mounted` is true;
   FastAPI does not run lifespans of mounted sub-apps, so if that wiring is
   wrong every real MCP request 500s while the unit tests still pass. Verify
   with a live client, not just pytest.
3. **`test_govern_then_verify_round_trip` is the load-bearing test.** It runs
   the real pipeline and real crypto end to end. If it fails, do not adjust the
   test — the discrepancy is in the pipeline or in
   `axiom.mcp.tools._payload_hash_matches`.
4. **Coverage gate is ≥80%.** `tests/mcp/` should carry the new package
   comfortably, but `transport.py`'s stdio path (`_serve_stdio`, `main`) is
   thin on coverage — add tests there if the gate is close.

Also confirm the **ADR-028 behaviour change** did not break existing data:

```sql
SELECT count(*) FROM receipts
 WHERE evidence_nonce IS NULL
    OR evidence_ciphertext IS NULL
    OR evidence_key_id IS NULL;
```

`GET /v1/verify/{id}` previously reported `payload_hash_matches` as
unconditionally `true` (it was hardcoded). It now recomputes
`sha256(nonce || ciphertext || key_id)`. Any receipt returned by that query
will flip from `verified: true` to `verified: false` — which is the correct
answer, but you want to know the count before deploying, not after a customer
asks. If the count is non-zero, decide deliberately: backfill, or document that
pre-Phase-7 receipts are unverifiable.

---

## Part 1 — `generic_proxy` credential injection

`GET|POST|... /v1/proxy/{proxy_target:path}` in `apps/backend/src/axiom/gateway/app.py`
currently strips `Authorization` and never calls `inject_credentials`. That is
**fail-safe, not fail-open** — it refuses to forward credentials to arbitrary
URLs rather than leaking them — but it means the advertised "point the gateway
at any URL and let it supply the vault credential" workflow does not work.

Named provider routes (`POST /v1/{provider}/{path}`) already do this correctly
via `gateway/vault.py:inject_credentials`. The task is to extend that to the
generic path **without** turning the gateway into a credential oracle.

Requirements:

- The caller names which vault credential to use — for example a
  `X-Axiom-Vault-Key: <key-name>` header. Never infer it from the target host;
  host-based inference means a request to an attacker-controlled URL can select
  a credential the caller was not entitled to.
- Resolve the named key **within the caller's project only** (`APIKeyContext.project_id`),
  and return not-found rather than forbidden for a key in another project,
  matching the enumeration-resistance posture used elsewhere.
- Keep `assert_public_http_url` (SSRF guard) ahead of any credential resolution,
  so a blocked target never causes a vault read.
- Governance still runs first and unchanged: deny → 403, hold → 202, allow →
  forward and seal a receipt. A credential must never be injected into a request
  that was not allowed.
- The receipt must record which vault key was used (`vault_key_id`), as the
  named-provider path already does.
- When no vault key header is supplied, preserve today's behaviour exactly:
  strip `Authorization`, inject nothing. This must remain the default.

Tests: credential injected only on allow; not injected on deny or hold; SSRF
target rejected before any vault access; cross-project key resolves to not
found; no header means no injection and no `Authorization` passthrough; the
receipt records the vault key id.

---

## Part 2 — Dead branch in the classifier

`gateway/classifier.py:42` reads:

```python
if p in _REGISTRY_PROVIDERS and p != "custom":
```

`_REGISTRY_PROVIDERS` is `frozenset(get_all_provider_names())`, and `"custom"`
is not a key in `PROVIDERS` (13 entries: groq, openai, anthropic, xai, google,
perplexity, openrouter, together, fireworks, deepseek, mistral, cerebras,
replicate). The `and p != "custom"` guard can never be false when the first
condition is true. Delete it, keep the separate `if p == "custom":` branch below
which is the real handler.

Confirm with a test that `classify_gateway_request` still routes `custom` to
`tool.http.custom` with host-derived risk.

---

## Part 3 — Update the backlog doc

`docs/phases/PHASE_6_7_BACKLOG.md` describes three open items. Two are already
done and the doc is now misleading:

- **Provider fabric unification — DONE.** There is a single
  `gateway/provider_registry.py` with 13 providers including the previously
  missing `replicate`, `together`, `mistral`; `classifier.py` reads it via
  `get_all_provider_names()`; and `app.py` serves one generic
  `@app.post("/v1/{provider}/{path:path}")` route rather than hand-written
  per-provider routes. The three-way vault/gateway/route mismatch the backlog
  describes no longer exists.
- **Classifier `custom` branch** — closed by Part 2.
- **Generic proxy safety** — closed by Part 1.

Rewrite the doc to reflect what actually shipped, or delete it and record the
outcome in `docs/decisions.md`. A backlog that lists completed work as open
costs you a re-investigation every time someone reads it.

---

## Definition of done

- `./axiom test` passes: ruff, format, mypy, pytest ≥80% coverage, tsc, build, vitest.
- `lint-imports` reports 5 contracts kept, 0 broken.
- A real MCP client completes `govern_action` → `verify_receipt` against the
  running server (config block in `docs/MCP.md`).
- The legacy-receipt query above has been run and its result recorded.
- `generic_proxy` injects vault credentials only on an allowed request with an
  explicit key header, and the receipt records which key.
