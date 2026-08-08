# Phase 6.7 — Provider Fabric & Gateway (closed 2026-08-06)

**Status: closed.** All three items opened by the Phase 6.5 recon have shipped.
This file is kept as the record of what was done; it is no longer a list of
open work. Do not re-investigate these as if they were outstanding.

## 1. Provider fabric unification — DONE

The three-way disagreement between vault detection, the gateway provider table,
and hand-written per-provider routes no longer exists.

- `gateway/provider_registry.py` is the single source of truth, with 13
  providers: `anthropic`, `cerebras`, `deepseek`, `fireworks`, `google`,
  `groq`, `mistral`, `openai`, `openrouter`, `perplexity`, `replicate`,
  `together`, `xai`. The previously missing `replicate`, `together` and
  `mistral` are all present.
- `classifier.py` reads the registry via `get_all_provider_names()` instead of
  keeping its own copy.
- `gateway/app.py` serves one generic `@app.post("/v1/{provider}/{path:path}")`
  route rather than hand-written per-provider routes.
- Every `llm`-kind service the vault can detect has a matching registry entry,
  so a credential can no longer be stored for a provider the gateway cannot
  route to.

**Not shipped:** `cohere` appeared in the original indicative scope but was
never added. It is absent from both the registry and the vault detection rules,
so the two remain consistent. Adding it is new work, not leftover work.

## 2. Classifier `custom` branch — DONE

`classifier.py` carried `if p in _REGISTRY_PROVIDERS and p != "custom":`. The
`and p != "custom"` guard was provably dead: `"custom"` is not a key in the
registry, so the first condition is already false for it and the second could
never change the outcome. The guard is deleted; the separate `if p == "custom":`
branch below it remains the real handler for generic-proxy traffic.

`tests/unit/test_gateway/test_gateway_classifier.py` pins both halves of that
reasoning: `test_custom_is_not_a_registry_provider` asserts the invariant that
made the guard dead, and `test_custom_risk_is_derived_from_host` asserts
`custom` still classifies as `tool.http.custom` with risk derived from the
target host rather than a constant.

## 3. Generic proxy safety — DONE

`/v1/proxy/{target}` previously stripped `Authorization` and never called into
the vault. That was fail-safe, but it meant the advertised "point the gateway at
any URL and let it supply the credential" workflow did not work.

It now injects credentials under strict conditions:

- **Explicit only.** The caller names the credential with an
  `X-Axiom-Vault-Key: <key-name>` header. The target host is never used to infer
  which key to use — host-based inference would let a request to an
  attacker-controlled URL select a credential the caller was not entitled to.
- **Default unchanged.** With no header, behaviour is exactly as before:
  `Authorization` is stripped and nothing is injected.
- **Ordering is load-bearing.** `assert_public_http_url` (SSRF) runs first, then
  governance; the vault is read only after an `allow`. A blocked target never
  causes a vault read, and a denied (403) or held (202) request never receives a
  credential.
- **Tenancy.** The key resolves within the caller's own vault only. A key
  belonging to another tenant returns not-found, never forbidden, matching the
  enumeration-resistance posture used elsewhere.
- **Auditable.** The sealed receipt records `vault_key_id` — which key was used,
  never the secret itself.

Covered by `tests/unit/test_gateway/test_generic_proxy_vault.py`, including
mutation-checked assertions for injection-on-allow and cross-tenant isolation.

---

## Known limitation (carried forward, not part of 6.7)

`VaultKey` is scoped by `user_id`, not `project_id` — there is no `project_id`
column on the table. The generic proxy therefore scopes lookups by
`APIKeyContext.created_by_user_id`, the same boundary the named-provider path
already uses. This isolates tenants in the normal case, but a single user who
owns API keys in two different projects can reach the same vault key from
either. Making the vault genuinely project-scoped is a schema change and belongs
in its own phase.
