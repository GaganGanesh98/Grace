# Phase 6.7 — Backlog (Provider Fabric & Gateway)

Items deferred from Phase 6.5 recon. **Do not implement in 6.5.**

## Classifier — `custom` branch (`classifier.py`)

- Around line 40: `p in PROVIDERS and p != "custom"` — `custom` is not in `PROVIDERS`, so this condition may not behave as intended. Review when touching gateway classification (scheduled for Provider Fabric work).

## Three-mechanism mismatch (vault vs gateway)

- **Vault** `PROVIDER_PATTERNS` / `detect_provider()` vs **gateway** `PROVIDERS` vs **named routes** in `gateway/app.py` can disagree (e.g. Replicate detected in vault but missing from `PROVIDERS`; Together/Cohere/Mistral in registry without `/v1/...` routes).
- **Phase 6.7 — Provider Fabric Unification** (indicative scope): add Replicate to `PROVIDERS`; add `/v1/replicate`, `/v1/together`, `/v1/cohere`, `/v1/mistral` mirroring existing patterns; optionally teach `/v1/proxy/...` to honor vault credentials with SSRF + policy checks; consolidate into a single source of truth.

## Generic proxy safety

- `generic_proxy` strips `Authorization` and does not call `inject_credentials`. Treat as unsafe for “paste any URL + vault key” until Phase 6.7 addresses it.
