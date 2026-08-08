# Architecture Decision Records (Grace)

## ADR-001 — Python 3.13 (not 3.14) for Phase 1–2

**Status:** Accepted
**Context:** Phase 2 will add native-code cryptography; wheel availability matters.
**Decision:** Pin the backend to CPython **3.13.x** via `requires-python` and `uv python pin`.
**Consequences:** We avoid early 3.14 ecosystem gaps; CI and devcontainers must supply 3.13.

---

## ADR-002 — FastAPI for the public API

**Status:** Accepted
**Context:** Need async HTTP, validation, and first-class OpenAPI for agent integrators.
**Decision:** Use **FastAPI** (0.115+) with Pydantic v2 models for request/response.
**Consequences:** Excellent `/docs` DX; we must discipline ourselves to keep business logic in services, not routers.

---

## ADR-003 — PostgreSQL 18

**Status:** Accepted
**Context:** Phase 2 wants strong UUID and indexing story; team standardized on PG18 for dev/prod alignment.
**Decision:** Run **postgres:18** in Compose; use `uuidv7()` server defaults where supported.
**Consequences:** Local dev must run PG18; migrations assume PG18 features where used.

---

## ADR-004 — SQLAlchemy 2.0 async (not sync ORM)

**Status:** Accepted
**Context:** High concurrency API + async stack end-to-end.
**Decision:** **SQLAlchemy 2.0** with `AsyncSession`, **asyncpg**, and Alembic async `env.py`.
**Consequences:** All DB access paths must be async; sync drivers are out of scope.

---

## ADR-005 — Uvicorn as the ASGI server (Phase 1)

**Status:** Accepted
**Context:** Alternative Rust/Granian stacks are evolving quickly.
**Decision:** Use **Uvicorn** for Phase 1; re-evaluate Granian or multi-worker patterns in Phase 4.
**Consequences:** Known, boring deployment path; tuning is standard asyncio + worker count.

---

## ADR-006 — No job queue in Phase 1

**Status:** Accepted
**Context:** Phase 1 is CRUD + auth; no long-running govern jobs yet.
**Decision:** No Celery/Arq/Redis Queue—**inline async** service calls only.
**Consequences:** Phase 2 pipeline will introduce a queue or worker tier as latency and reliability demand.

---

## ADR-007 — Next.js 14 App Router

**Status:** Accepted
**Context:** Need stable App Router, RSC-friendly data loading, and shadcn compatibility.
**Decision:** **Next.js 14.2+** App Router only (no Pages Router).
**Consequences:** Middleware and Route Handlers are first-class for auth cookie BFF patterns.

---

## ADR-008 — Monorepo (`apps/backend`, `apps/frontend`)

**Status:** Accepted
**Context:** Single founder/small team velocity; atomic API + UI changes.
**Decision:** One git repo with `apps/*` and shared `docs/`, `scripts/`.
**Consequences:** CI must matrix backend/frontend; version coupling is explicit.

---

## ADR-009 — JWT in httpOnly cookies for browser sessions

**Status:** Accepted
**Context:** Storing tokens in `localStorage` is XSS-friendly.
**Decision:** Browser auth uses **httpOnly** cookies set by Next Route Handlers after successful FastAPI auth; dashboard RSC talks to FastAPI server-side with Bearer derived from cookies.
**Consequences:** `/docs` and API clients still use Bearer; CORS + cookie rules must stay strict.

---

## ADR-010 — OWNER / ADMIN / MEMBER project roles

**Status:** Accepted
**Context:** Multi-tenant projects need coarse RBAC before fine-grained policy execution.
**Decision:** Three roles with numeric ordering; **OWNER** required for destructive tenant operations (e.g. project delete).
**Consequences:** Some flows (OWNER transfer, billing) are deferred; guards must prevent ownerless projects.

---

## ADR-011 — Docker host port remapping when 5432/6379 are busy

**Status:** Accepted
**Context:** Developer machines may already run Postgres/Redis on default ports.
**Decision:** Compose maps **5433→5432** and **6380→6379**; `.env.example` documents matching URLs.
**Consequences:** Docs and scripts must say “adjust ports if you free 5432/6379”; production uses standard ports behind the platform.

---

## ADR-012 — First user bootstrap via default personal project

**Status:** Accepted
**Context:** “First signup is OWNER” is ambiguous without a project scope.
**Decision:** On first **user** registration, create a default **personal** project and OWNER membership; additional users start as accounts only until invited as MEMBER by default.
**Consequences:** OWNER semantics attach to **project membership**, not a global site role.

---

## ADR-013 — slowapi for rate limiting (Redis-backed)

**Status:** Accepted
**Context:** Phase 1.5 requires per-IP and per-route limits without adding new infrastructure beyond Redis.
**Decision:** Use **slowapi** with `storage_uri` pointed at `REDIS_URL`, default **60/min/IP**, stricter decorators on `login`, `signup`, and `google/callback`.
**Consequences:** Tests that hammer `login` may interact with the global cap; lockout-focused tests disable the limiter via `enabled=False` on the shared `Limiter` instance for the duration of the test (restored by pytest).

---

## ADR-014 — bcrypt cost 12 (unchanged from Phase 1)

**Status:** Accepted
**Context:** Password hashing choice was fixed in Phase 1; Phase 1.5 must not swap algorithms.
**Decision:** Keep **bcrypt** via passlib at cost factor **12**.
**Consequences:** Argon2id remains a Phase 5+ discussion if compliance demands it.

---

## ADR-015 — Account lockout 5 fails / 15 minutes (per email)

**Status:** Accepted
**Context:** Brute-force resistance for password login without CAPTCHA.
**Decision:** Track failures in Redis (`lockout:fails:{email}` + `lockout:locked:{email}`), **normalized email**, threshold **5**, window **15 minutes**; successful login clears counters.
**Consequences:** Legitimate users who typo repeatedly may be blocked; support playbook is “wait 15 minutes or clear Redis in controlled environments.”

---

## ADR-016 — Request body cap 1 MiB (Content-Length)

**Status:** Accepted
**Context:** DoS via huge JSON bodies on state-changing routes.
**Decision:** `BodySizeLimitMiddleware` rejects requests when `Content-Length` exceeds **1 MiB** with **413** and a stable JSON error shape.
**Consequences:** Chunked uploads without a length header are not fully bounded (ASGI streaming cap deferred to Phase 2).

---

## ADR-017 — Strict baseline security headers + CSP

**Status:** Accepted
**Context:** Reduce XSS/clickjacking and MIME confusion for API responses.
**Decision:** Add `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, and strip `Server` on every response.
**Consequences:** If the browser UI ever needs relaxed CSP, adjust explicitly (Phase 2+) rather than weakening silently.

---

## ADR-018 — SSRF helper scope (IP literals only in Phase 1.5)

**Status:** Accepted
**Context:** No production route yet accepts arbitrary URLs for server-side fetch; Phase 1.5 still ships the guard early.
**Decision:** `validate_external_url()` blocks private/link-local/metadata IP literals for `http(s)`; DNS rebinding and full URL-fetch pinning are **out of scope** until outbound integrations land.
**Consequences:** Call sites must still use safe HTTP clients and re-validate at fetch time in Phase 2+.

---

## ADR-019 — Pre-commit + CI parity (TruffleHog CI-only)

**Status:** Accepted
**Context:** Contributors need fast local hooks; CI must still catch secret regressions.
**Decision:** `.pre-commit-config.yaml` runs Ruff, mypy, Gitleaks, and repo-local guard scripts; **TruffleHog runs in GitHub Actions only** because the official pre-commit hook builds a large Go toolchain and failed under constrained CI sandboxes.
**Consequences:** Developers who bypass pre-commit are still scanned on push via the `secrets` job.

---

## ADR-020 — Coverage gate + omitted modules + npm audit pragmatism

**Status:** Accepted
**Context:** An 80% **combined line+branch** gate could not be met without either a Next.js major bump or disproportionate OAuth integration tests.
**Decision:** (1) Measure **line coverage only** (`branch = false` in Coverage.py) with `--cov-fail-under=80`; (2) **omit** `src/axiom/services/google_oauth.py` from coverage totals (covered indirectly via security tests and runtime); (3) run `npm audit --audit-level=critical` in CI while Dependency Review still fails on **high** for lockfile PRs.
**Consequences:** Remaining **high** Next.js advisories must be tracked explicitly until a planned framework upgrade; Google OAuth file is excluded from the numerical gate but not from type-checking or review.

---

## ADR-020 (addendum) — CLOSED in Phase 1.6

The three accepted deviations from ADR-020 are now closed:

- `google_oauth.py` removed from coverage omit; now at ≥90% via mocked JWKS (`pytest-httpx`) and deterministic RSA fixtures.
- Branch coverage enabled; global gate is `--cov-branch` with `--cov-fail-under=80` (combined line+branch).
- `services/auth.py` gated at ≥95% per-file in CI.

The Next.js 14 → 16 upgrade (ADR-020 item 4) remains deferred to Phase 3 frontend work.

---

## ADR-021 — Import-linter enforces layered architecture

**Status:** Accepted
**Context:** Prevent v1-style cross-cutting imports (routers importing each other, services importing routers, models pulling in heavy service layers).
**Decision:** [import-linter](https://github.com/seddonym/import-linter) contracts checked in CI from `apps/backend` with `uv run lint-imports --config ../../.importlinter`. Phase 1.6 ships two contracts: **models never import services, routers, or middleware**, and **layered architecture** (`routers` → `services` → `models` → `core`). Additional forbidden contracts for `axiom.services.crypto` (leaf) and `axiom.services.pipeline.protocols` (pure interfaces) are documented in `.importlinter` comments and will be enabled once those packages exist in Phase 1.75 — import-linter requires source modules to exist on disk before they can be enforced.
**Consequences:** Half a day setup cost, permanent architectural discipline. Any future cross-cutting import that violates an active contract causes CI to fail with a clear message.

---

## ADR-022 — Use react-hook-form Controller for Base UI form primitives

**Status:** Accepted
**Context:** Base UI `FieldControl` / `Input` wrapper does not forward the native input ref in a way RHF’s `register()` can capture, so submitted values can be missing and Zod reports `undefined` for required strings (silent UX failure). Discovered and fixed in Phase 2.3; see `apps/frontend/components/auth/auth-text-field.tsx`.
**Decision:** For **auth** and **future** forms that use Base UI primitives, use **RHF `Controller`** with a **native `<input>`** (or other native control) styled with the same design tokens as our UI kit. **Do not** spread `register()` onto Base UI `Input` / field parts that wrap `FieldControl`.
**Consequences:** Consistent form pattern across Phase 3+ forms. Slightly more ceremony than `register()` alone. Eliminates a class of silent form bugs from ref merging and controlled/uncontrolled edge cases.

**Addendum (Phase 2.3 — Google ID token):** Google’s ID tokens may include an `at_hash` claim; `python-jose` verifies it only when the OAuth **`access_token`** from the same token response is passed into `jwt.decode`. Production `exchange_code` must pass that access token into `verify_google_id_token`; isolated tests without an access token disable `verify_at_hash` for that decode.

---

## ADR-024 — OAuth callback single-fire guard (React Strict Mode)

**Status:** Accepted
**Context:** React 18 Strict Mode double-invokes `useEffect` in development. Idempotent effects tolerate this; **non-idempotent** effects that trigger a **single-use** server resource (e.g. OAuth CSRF `state` stored once in Redis and deleted on first use) cause a race: the first invocation consumes the state, the second fails with “Invalid or expired OAuth state” even when a parallel request eventually succeeds.
**Decision:** On callback pages that POST once per browser navigation, use a **`useRef` boolean guard** set to `true` **synchronously before** starting the async work. **Do not** put the ref in the effect dependency array. **Do not** relax server-side single-use state validation. See `apps/frontend/app/auth/callback/google/google-callback-inner.tsx` (`GoogleCallbackInner`).
**Consequences:** Dev UX matches production for OAuth return. Server CSRF semantics stay strict (one state, one redemption). Slight pattern duplication for any future single-use callback routes (same guard). Related form pattern: **ADR-022** (RHF `Controller` + native inputs vs Base UI `register()`).

---

## ADR-025 — Single `./axiom` CLI for local dev orchestration

**Status:** Accepted
**Context:** Phase 1 introduced checked-in **`dev.sh`** and **`stop-dev.sh`** helpers under **`scripts/`** (removed Phase 2.4). By Phase 2.3 the shell surface was growing (manual port cleanup, DB reset, multiple terminals). The old **`dev.sh`** used **`sudo docker compose`**, wrote PIDs under **`/tmp`**, and did not health-gate the app tier. Port expectations diverged from compose (**5433** / **6380** on the host).
**Decision:** Consolidate local dev orchestration under a single **`./axiom <cmd>`** entrypoint (pure bash, CWD-independent path resolution, **no sudo**). Hard-require **docker group** membership with a fixed preflight error pointing at **`docs/dev-setup.md`**. Use actual **host-published ports** (5433, 6380, 8000, 3000) for status, health checks, and port policy. **`./axiom stop`** uses **`docker compose stop`** (containers + volumes preserved). **`./axiom fresh`** is the only **`docker compose down -v`** path. **`./axiom test`** runs the same gates as CI (ruff, format, mypy, pytest+coverage, tsc, build, vitest), with **`./axiom test --fast`** for pytest + vitest only.
**Consequences:** One place to learn and maintain. Clear namespace for future subcommands. **Intentional behavior change** from the legacy **`stop-dev.sh`** helper (it lived under **`scripts/`**), which ran **`docker compose down`** for routine stop—documented in **`docs/dev-setup.md`** troubleshooting and here: developers who relied on `down` for every stop should use **`./axiom stop`** for fast, volume-preserving stops and **`./axiom fresh`** only when volumes must be wiped. Host ports **5433** / **6380** must stay reflected in docs and tooling without editing `docker-compose.yml` for this contract.

---

## ADR-026 — MCP reuses project API keys instead of a passport credential

**Status:** Accepted
**Context:** Phase 7.0 exposes governance over the Model Context Protocol. The obvious precedent (AXIOM-BRAIN's `govern/passports.py`) issues a dedicated short-lived "passport" credential for MCP sessions, and "passport" is arguably the better noun for an agent identity than "API key". Adopting it would mean a second credential type with its own minting, storage, expiry, revocation, and scope model — and a second place for any of those to be wrong.
**Decision:** MCP authenticates with the existing **`axm_live_` / `axm_test_` project API keys** via `axiom.services.api_key.service.verify_key`. Two new scopes gate the surface: **`mcp:read`** (`check_policy`, `verify_receipt`, `get_receipt`, `list_policies`) and **`mcp:write`** (`govern_action`). These are **deliberately distinct from `govern:write`**, so a key minted for the HTTP API does not silently become an MCP credential. The principal is resolved once per session and held in a context variable, but **write tools re-verify the key against the database on every call** (`auth.reverify_for_write`) so revocation is immediate rather than session-scoped.
**Consequences:** One credential system, one revocation path, one scope model, no new secret storage. Granting MCP access is an explicit act (mint a key with MCP scopes) — slightly more friction than implicit inheritance from `govern:write`, which is the correct trade for a governance product. Existing keys do **not** gain MCP access on upgrade. If short-lived agent credentials are ever needed, they should be added as an expiry/rotation feature of the existing key model rather than a parallel type.

---

## ADR-027 — MCP tool responses lead with a natural-language verdict

**Status:** Accepted
**Context:** MCP tool results are consumed by a language model, not by application code with a `switch` on a status field. During Phase 7.0 design it was noted that a model skimming a JSON object will readily miss `{"verdict": "deny"}` among a dozen sibling keys and proceed with the action anyway — a governance layer that records the denial but does not achieve it.
**Decision:** Every MCP tool output model leads with a prose field (`decision` / `summary`) that states the outcome and the agent's resulting obligation as an imperative sentence ("DENIED. You must NOT perform this action…", "MODIFIED. You must NOT use your original action…"). Structured fields (`verdict`, `allowed`, `modification`) remain for programmatic consumers. `shadow` mode says so explicitly in that sentence so a non-blocking verdict is never mistaken for an allow. Tool *descriptions* likewise state obligations rather than describing return shapes, because the description is often all the model reads before deciding to call.
**Consequences:** Some redundancy between the prose and the structured fields, which is intentional. Any new MCP tool must follow the pattern. The `_decision_sentence` helper in `axiom.mcp.tools` is the single place this wording lives — changes to verdict semantics must update it or the prose will drift from the structured verdict.

---

## ADR-028 — `payload_hash_matches` verifies the evidence envelope

**Status:** Accepted
**Context:** `GET /v1/verify/{receipt_id}` advertises four independent checks and reports `verified = true` only when all four pass. Three were real (Ed25519 signature, ML-DSA-65 signature, RFC 6962 Merkle inclusion). The fourth was not: `payload_hash_matches = hashlib.sha256(canonical_bytes).digest() != b""  # always True`. It was hardcoded to pass, so a receipt whose stored evidence had been altered after signing would still verify — on the endpoint whose entire purpose is detecting exactly that. Discovered in Phase 7.0 while implementing the MCP `verify_receipt` tool.
**Decision:** Recompute the hash Stage 5 (Evidence) actually defines and compare it to the stored value:

```
payload_hash = sha256(evidence_nonce || evidence_ciphertext || evidence_key_id.encode("utf-8"))
```

All three inputs are persisted on the `receipts` row, so this is checkable without decrypting the evidence or exposing ciphertext to the caller. It is **not** the hash of the canonical signed body — the signed body *contains* the base64 payload_hash, so hashing it would be circular. Missing evidence components **fail closed** (`False`): an unverifiable receipt is not a verified one. Applied identically in `routers/verify.py` and `axiom.mcp.tools._payload_hash_matches`.
**Consequences:** This is a behaviour change to a public endpoint. Receipts whose evidence envelope does not reproduce the stored hash — including any legacy receipt written without complete evidence columns — will now report `verified: false` where they previously reported `true`. That is the correct answer, but it means the change can surface pre-existing data problems on deploy; check for receipts with null `evidence_nonce` / `evidence_ciphertext` / `evidence_key_id` before shipping. The check now genuinely detects post-hoc tampering with stored ciphertext, key id, or nonce (regression tests in `tests/mcp/test_mcp_tools.py`).

---

## ADR-029 — Grace rebrand renames user-facing copy only; identifiers with a contract are deferred

**Status:** Accepted
**Context:** The product is Grace; the codebase says AXIOM in roughly 1100 places. Those occurrences are not equivalent. Some are copy on a page, some are a Python module path, some are a wire header a deployed client already reads, and one — the `axm_live_` / `axm_test_` key prefix — is data sitting in `api_keys.key_prefix` in production. A repo-wide `sed s/axiom/grace/g` would break `uvicorn axiom.main:app`, the Alembic env, the installed console scripts, and every API key in the database simultaneously, with no way to bisect which rename caused which failure.
**Decision:** Phase 8.0 renames only what carries no runtime contract:

- **User-facing copy** — page titles, wordmarks, body strings, the FastAPI/gateway OpenAPI titles, the `explain_no_policy` response text, `DEV_PROJECT_NAME`, and prose in current-state docs.
- **Frontend-internal identifiers** — the `lib/events` context/hook filenames and their exported types, and the `--axiom-font-scale` CSS custom property.

Everything below is **deliberately deferred**, each to its own phase with its own verification:

| Thing | Count / risk | Why it cannot be a find-replace |
|---|---|---|
| `axiom` Python package | 1067 import sites | Changes `uvicorn axiom.main:app`, `alembic/env.py`, `[project.scripts]`, the `packages/axiom-sdk` distribution name, and the namespace-collision guard in `tests/conftest.py`. |
| `axm_live_` / `axm_test_` | 28 code sites + **live DB rows** | This is data. `api_keys.key_prefix` stores the first 16 chars and `verify_key` narrows on it; changing the constant orphans every existing key. Needs a dual-prefix accept window or a deliberate re-mint. |
| `AXIOM_*` env vars (~40) | `.env`, Railway, docker-compose, CI | Every deployment target has these set. Needs `AliasChoices("GRACE_X", "AXIOM_X")` for a compat window, then a later removal. |
| `X-Axiom-Receipt-Id`, `X-Axiom-Vault-Key`, `X-Axiom-Agent-Id`, `X-Axiom-Signature` | wire protocol | Emitted by the gateway, read by clients and the agent worker. Needs dual-emit / dual-read before the old form is dropped. |
| `axiom-postgres`, `axiom-redis`, `axiom_pg_data`, DB name/user `axiom` | local + deployed state | Renaming the volume orphans the data; renaming the DB user needs a migration. |
| `./axiom` CLI | muscle memory + docs | Cheap, but should land with the package rename so there is one cutover, not two. |

**Sequencing when Tier 3 is picked up:** package rename first (largest, purely mechanical, fully covered by the test suite), then env vars behind aliases, then headers with dual-emit, and the key prefix **last** because it is the only one that touches stored data.

**Consequences:** The running app shows no user-visible "AXIOM", while the code, wire protocol, env, and stored credentials continue to say axiom — an intentional, documented inconsistency rather than a half-finished rename. Two further items were left deliberately and are worth knowing about: the localStorage key `"axiom-font-scale"` in `lib/axiom-storage.ts` is persisted client state, and renaming it would silently reset every user's font-scale preference; and the `text-axiom-*` Tailwind utilities and `--axiom-*` token bridge in `globals.css` are internal but touch enough components that they belong with the Part 4 design work, not a rename commit. Historical documents (`docs/ANTIPATTERN_LIBRARY.md`, `docs/v1-salvage-report.md`) keep their AXIOM references, because rewriting the product name inside a post-mortem — including a quoted V1 tagline and the named "AXIOM UNIVERSAL PROTOCOL" anti-pattern — would falsify the record.

---

## ADR-030 — Envelope encryption with per-row DEKs, AAD binding, and a derived vault KEK

**Status:** Accepted
**Context:** `services/vault.py` encrypted every user credential with `get_signing_keys().evidence_key` — the same AES-256 key that encrypts receipt evidence. The two have different threat models and different lifetimes: credential encryption wants rotation on a schedule and immediately after suspected exposure, while evidence encryption is bound to the audit trail, where rotation means re-encrypting history. Sharing one key meant neither could rotate without breaking the other. Worse, `crypto/vault.py` stored ciphertext as an opaque `nonce || ciphertext` blob with no key identifier, so nothing recorded which key encrypted which row — rotation was not awkward, it was unimplementable without decrypting everything under a guessed key.

**Decision:** Four choices, each earning its place.

**Per-row DEK.** Each credential gets its own random 256-bit data key; the KEK only ever wraps that DEK. Rotating the KEK is an unwrap/re-wrap of 32 bytes per row — it never touches credential plaintext, never contacts the upstream provider, and runs online. `envelope.rewrap` returns the input's `ciphertext` object unchanged and a test asserts byte-identity, because the moment rotation starts decrypting payloads it stops being a routine operation. This single decision is what makes rotation a non-event.

**Key identifier on every row.** `vault_keys.kek_id` records which KEK wrapped the DEK. Readers dispatch on it, so old and new keys coexist during a rotation and a key is retirable once its row count reaches zero. `GRACE_VAULT_KEK_PREVIOUS_B64` holds retired keys so a rotation need not be atomic. Reads resolve by recorded id and **raise** on an unknown id rather than falling back to the active key: a row we cannot attribute is a fact worth surfacing.

**AAD binding.** `crypto/aes_gcm.py` already accepted `associated_data` and `crypto/vault.py` passed `None`. Each payload is now bound to `grace/vault/v2|{vault_key_id}|{user_id}`, and each wrapped DEK to its own `kek_id`. An attacker with database write access cannot move a ciphertext between rows or users — the GCM tag fails. This costs nothing and closes a class of attack confidentiality alone does not.

**Purpose separation by derivation, with explicit override.** When `GRACE_VAULT_KEK_B64` is unset the vault KEK is `HKDF-SHA256(ikm=evidence_key, salt=None, info=b"grace/vault-kek/v1", 32)`. Local dev keeps working with zero new configuration, and the derived key is cryptographically distinct, so a vault compromise does not hand over evidence decryption. State plainly what this is: **purpose separation, not root separation** — the evidence key still implies the vault KEK. Production sets an independent `GRACE_VAULT_KEK_B64`, and a KEK byte-identical to the evidence key refuses to boot rather than silently undoing the phase.

**Rejected: per-tenant keys.** This design invites "why not per-tenant DEK wrapping too?" Because there is one tenant. The extension is natural in this shape — `Purpose` grows a tenant dimension and `kek_registry` resolves per tenant — and the point of doing the envelope work now is that the extension stays cheap when it is actually needed, not that it should be built speculatively.

**Consequences:** `vault_keys` gains `scheme`, `kek_id`, and `wrapped_dek`, all nullable-or-defaulted so the migration is online-safe. Pre-8.2 rows stay readable as `legacy/v1` — which means the evidence key is still needed to read part of the vault until `axiom keys migrate-vault --apply` reports zero legacy rows, so the backfill is not optional if the separation is to mean anything. The migration's `downgrade` refuses while envelope rows exist, because dropping `wrapped_dek` destroys the only route back to their plaintext. `kek_registry` is a crypto leaf (import-linter contract 3) and therefore cannot import `receipt.keys`; the dependency is inverted via `set_evidence_key_provider`, which also preserves dev auto-generation. Rotation, backfill, and verification exist as `axiom keys` subcommands with a runbook (`docs/runbooks/key-rotation.md`) rather than as a design sketch — a rotation procedure first attempted during an incident is one that fails.

---

## ADR-031 — One governed-action surface for external orchestrators

**Status:** Accepted
**Context:** The n8n integration was single-purpose. `services/escalation/` plus `POST /webhooks/n8n/escalation-result` proved that a machine caller authenticated by HMAC over the raw body works well, but it exists only to resolve an escalation Grace itself started. Any other n8n workflow — a finance approval, an ops runbook, an outbound email — that wanted a governed action had no entry point at all: the alternatives were minting a project API key and hand-rolling the `/v1/governance/govern` call in a Code node, or skipping governance. Meanwhile the governed-action sequence (chain → intent → context → policy → verdict → pending receipt → hold handling → post-commit dispatch) lived inline in `routers/v1/governance.py`, so a second caller would have meant a second copy of the hold semantics and the shadow-mode masking rule.

**Decision:** Generalise the pattern into one reusable surface, with four choices worth naming.

**Extract the path into a service first.** `services/governance/execute.py::execute_governed_action` now owns the sequence and both the HTTP router and the webhook call it; a third caller (MCP) is foreseeable and gets it free. Shadow-mode masking is decided in exactly one place and returned as `response_verdict`, because the failure mode here is two surfaces disagreeing about what a policy said — which in a product whose output is an audit trail is worse than either answer being wrong. This is contract 5 in `.importlinter` applied to a new delivery mechanism: a surface consumes services, it does not re-implement them.

**A separate secret, `GRACE_N8N_ACTION_SECRET`.** The escalation callback can only resolve a receipt Grace already created. This endpoint can *originate* one, for any project named in the body — there is no API key narrowing it to a tenant, because the caller is a workflow, not a principal. Different blast radius, different key, and no fallback: unset returns `503` rather than quietly accepting the callback secret. Leaking the weaker secret must not confer the stronger capability.

**Idempotency keyed on the orchestrator's run id.** n8n retries on timeout, on 5xx, and when a human clicks "retry execution", reusing `$execution.id` each time. Without a claim, one real-world action produces several receipts, and the chain then asserts something false about how many times the action was governed — worse than not recording it. `SETNX` on `axiom:n8n:action:{workflow_id}:{workflow_run_id}` holds an in-flight sentinel, then the receipt id, for 24h. A replay re-reads the receipt from Postgres and returns it verbatim with `replayed: true`; a concurrent duplicate gets `409` rather than racing to a second receipt. Redis rather than a table because it is TTL'd cache-shaped state that must be checked *before* the transaction, and losing it degrades to a duplicate receipt rather than to data loss — the same reasoning as the rate limiter.

**Rejected: modelling the workflow.** It is tempting to store status, step position, or a resumption token so Grace can tell you where a workflow is. That is AP-1.8, "workflow orchestration creep", and it is recorded as a V1 failure mode for a reason. Grace stores the run id long enough to recognise a replay and nothing else. It does not schedule these calls, does not retry on the workflow's behalf, and does not model branches. n8n owns orchestration; Grace answers one question about one action and leaves a receipt.

**Consequences:** Any n8n, Zapier, or Temporal workflow becomes governable by importing one sub-workflow and passing seven fields — no backend change per workflow, and no engineer required per department, which is the actual modularity win. `workflow_id` / `workflow_run_id` land in the intent's metadata, so "which workflow did this?" is answerable from the audit chain rather than from n8n's logs. The costs are real and worth stating: the endpoint trusts a shared secret to name its own `project_id`, so that secret is now tenant-crossing and belongs in the key-rotation runbook alongside the others; and the `correct` verdict is declared in the response contract and given a Switch branch while the current YAML policy engine only emits `allow` / `deny` / `hold`, so `corrected_parameters` is always null until a policy can rewrite parameters. Declaring it now keeps the wire contract and the imported workflow stable when that lands, at the cost of a branch that is dead today.
