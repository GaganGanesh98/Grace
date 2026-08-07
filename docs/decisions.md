# Architecture Decision Records (AXIOM V2)

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
