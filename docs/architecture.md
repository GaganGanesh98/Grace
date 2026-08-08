# Grace — Architecture (Phase 1)

## System overview

Grace Phase 1 is a monorepo SaaS foundation: a **FastAPI** backend with **PostgreSQL 18** and **Redis**, plus a **Next.js 14 (App Router)** frontend. The product goal is a cryptographic governance proof layer for AI agents; Phase 1 delivers authentication, tenancy (projects), agents, policies (empty shells), API keys, and audit events—without the govern pipeline or cryptography.

## Stack (Phase 1)

| Layer | Choice | Role |
|--------|--------|------|
| API | FastAPI + Uvicorn | HTTP API, OpenAPI docs, async request handling |
| Data | SQLAlchemy 2.0 async + asyncpg | Typed ORM, non-blocking Postgres access |
| Migrations | Alembic (async env) | Single revision for Phase 1 schema |
| Cache / sessions | Redis | OAuth `state`, refresh token handles, rate limiting |
| Auth | JWT (access + refresh), bcrypt, Google OAuth (Authlib-style params + httpx) | User identity and BFF-friendly token issuance |
| UI | Next.js 14, Tailwind, shadcn-style components | Login, signup, Google callback, minimal dashboard |

Rationale for major choices lives in `docs/decisions.md` (ADRs).

## Data model (text ERD)

- **users** — identity; `citext` email; optional `password_hash` (OAuth-only users); optional `google_sub`.
- **projects** — tenant; `slug` unique; `owner_user_id` → users.
- **project_members** — `(project_id, user_id)` unique; `role` ∈ {OWNER, ADMIN, MEMBER}.
- **agents** — per-project registry; unique `(project_id, slug)`.
- **policies** — per-project versioned shells; unique `(project_id, slug, version)`.
- **api_keys** — per-project; `key_prefix` + `key_hash`; full key shown once on create.
- **audit_events** — append-only style operational log (not Phase 2 cryptographic receipts).

## Request flow

```text
Browser
  → Next.js (pages + Route Handlers under /api/*)
       → sets httpOnly cookies after auth
       → server components call FastAPI with Bearer from cookie (dashboard data)
  → FastAPI (/api/v1/*, /healthz, /readyz)
       → SQLAlchemy → PostgreSQL
       → Redis (OAuth state, refresh storage)
```

Public API clients (tests, `/docs`) send `Authorization: Bearer` directly. The browser uses **httpOnly cookies** set by Next Route Handlers so JavaScript never reads JWTs.

## Auth flows

### Email + password

1. `POST /api/v1/auth/signup` or `POST /api/v1/auth/login` returns access + refresh tokens.
2. Next `POST /api/auth/signup|login` proxies to FastAPI and sets **httpOnly** `access_token` and `refresh_token` cookies (tokens are not echoed in JSON to the browser).
3. Authenticated calls use the access cookie (via RSC fetch to FastAPI) or Bearer in API tools.

### Google OAuth

1. `GET /api/v1/auth/google/authorize` returns Google URL and stores `state` in Redis.
2. Browser completes Google consent; Google redirects to `GOOGLE_REDIRECT_URI` (e.g. `/auth/callback/google`).
3. Frontend posts `code` + `state` to Next `POST /api/auth/google/callback`, which calls FastAPI; on success, cookies are set the same way as email login.

## Role model

Project roles are ordered **OWNER > ADMIN > MEMBER**. Endpoints use `RequireProjectRole` with a minimum rank. The first registered user receives a default personal project and OWNER membership (see ADR in `docs/decisions.md`).

## Phase boundaries

Phase 2 adds `/v1/govern`, signing, Merkle receipts, evidence vault, and policy pack content. Phase 1 intentionally keeps `policies.rules` as an empty array placeholder and UI as functional, not marketing-polished.

## Security architecture (Phase 1.5)

### Defense in depth

- **Layer 1 — Pre-commit:** standard hygiene hooks, Ruff (lint + format), mypy on `apps/backend/src`, Gitleaks, local hooks blocking broad `except` and `print()` in backend source.
- **Layer 2 — CI:** Ruff, mypy, pytest with **≥80% line coverage** on measured packages, `pip-audit --strict`, `npm audit` at **critical** severity (Next.js 14.x still reports *high* issues without a major upgrade; see ADR-020), Trivy filesystem (non-blocking exit code), TruffleHog + Gitleaks on each PR, CodeQL, GitHub Dependency Review, Dependabot.
- **Layer 3 — Runtime middleware:** `SecurityHeadersMiddleware` (CSP, HSTS, frame deny, nosniff, referrer policy, permissions policy, strip `Server`), `BodySizeLimitMiddleware` (1 MiB via `Content-Length`), `CorrelationIDMiddleware` + structlog with sensitive-field redaction, CORS allowlist, **slowapi** with Redis storage (default **60/min/IP**, **5/min** login, **10/min** signup and Google callback).
- **Layer 4 — Application:** bcrypt cost 12, **account lockout** (5 failed password attempts / 15-minute Redis window per normalized email), `hmac.compare_digest` for refresh-token user id check, JWT `alg=none` rejected before decode, Pydantic `extra="forbid"` on `PATCH /users/me`, SSRF URL helper for future outbound HTTP, Google ID tokens verified (audience + issuer) after code exchange, **404** for cross-tenant project access where the caller is not a member (enumeration resistance), generic **500** JSON without stack traces.

### OWASP API Top 10 (2023) coverage map

| OWASP | Risk | Automated proof |
|-------|------|-----------------|
| API1 | BOLA | `tests/security/test_owasp_api01_bola.py` |
| API2 | Broken authentication | `tests/security/test_owasp_api02_auth.py` |
| API3 | BOPLA | `tests/security/test_owasp_api03_bopla.py` |
| API4 | Resource consumption | Rate limit, pagination, body size tests |
| API5 | BFLA | `tests/security/test_owasp_api05_bfla.py` |
| API6 | Sensitive business flows | `tests/security/test_owasp_api06_sensitive_flows.py` |
| API7 | SSRF | `tests/security/test_owasp_api07_ssrf.py` + `test_ssrf.py` |
| API8 | Misconfiguration | `tests/security/test_owasp_api08_misconfig.py` + headers/CORS |
| API9 | Improper inventory | `tests/security/test_owasp_api09_inventory.py` |
| API10 | Unsafe third-party consumption | `tests/security/test_owasp_api10_third_party.py` |

### Hardening regression prevention

Every Phase 1.5 control above has a matching test under `tests/security/` (including `test_v1_sins.py` for the v1 sin list). CI runs the full backend suite on every PR; pre-commit blocks the most common foot-guns before commit.
