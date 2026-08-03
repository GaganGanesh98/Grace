# Phase 1 Plan — Foundation

## 3.1 Directory structure (final)

```
AXIOM-V2/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── axiom
├── scripts/
│   └── lib/
│       └── axiom-*.sh
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   └── phases/
│       └── phase-1-foundation.md
└── apps/
    ├── backend/
    │   ├── pyproject.toml
    │   ├── alembic.ini
    │   ├── alembic/
    │   │   ├── env.py
    │   │   ├── script.py.mako
    │   │   └── versions/
    │   │       └── <revision>_phase_1_foundation.py
    │   ├── src/
    │   │   └── axiom/
    │   │       ├── __init__.py
    │   │       ├── main.py
    │   │       ├── config.py
    │   │       ├── db.py
    │   │       ├── deps.py
    │   │       ├── core/
    │   │       │   ├── __init__.py
    │   │       │   ├── errors.py
    │   │       │   ├── security.py
    │   │       │   ├── responses.py
    │   │       │   └── pagination.py
    │   │       ├── middleware/
    │   │       │   ├── __init__.py
    │   │       │   └── logging.py
    │   │       ├── models/
    │   │       │   ├── __init__.py
    │   │       │   ├── base.py
    │   │       │   ├── user.py
    │   │       │   ├── project.py
    │   │       │   ├── member.py
    │   │       │   ├── agent.py
    │   │       │   ├── policy.py
    │   │       │   ├── api_key.py
    │   │       │   └── audit_event.py
    │   │       ├── schemas/
    │   │       │   ├── __init__.py
    │   │       │   ├── common.py
    │   │       │   ├── auth.py
    │   │       │   ├── user.py
    │   │       │   ├── project.py
    │   │       │   ├── member.py
    │   │       │   ├── agent.py
    │   │       │   ├── policy.py
    │   │       │   └── api_key.py
    │   │       ├── services/
    │   │       │   ├── __init__.py
    │   │       │   ├── auth.py
    │   │       │   ├── google_oauth.py
    │   │       │   ├── redis_client.py
    │   │       │   ├── users.py
    │   │       │   ├── projects.py
    │   │       │   ├── members.py
    │   │       │   ├── agents.py
    │   │       │   ├── policies.py
    │   │       │   ├── api_keys.py
    │   │       │   └── audit.py
    │   │       └── routers/
    │   │           ├── __init__.py
    │   │           ├── health.py
    │   │           ├── auth.py
    │   │           ├── users.py
    │   │           ├── projects.py
    │   │           ├── members.py
    │   │           ├── agents.py
    │   │           ├── policies.py
    │   │           └── api_keys.py
    │   └── tests/
    │       ├── conftest.py
    │       ├── test_healthz.py
    │       ├── test_auth_signup.py
    │       ├── test_auth_login.py
    │       ├── test_auth_google.py
    │       ├── test_auth_jwt.py
    │       ├── test_users_me.py
    │       ├── test_projects.py
    │       ├── test_members.py
    │       ├── test_agents.py
    │       ├── test_policies.py
    │       └── test_api_keys.py
    └── frontend/
        ├── package.json
        ├── package-lock.json
        ├── tsconfig.json
        ├── next.config.mjs
        ├── postcss.config.mjs
        ├── tailwind.config.ts
        ├── components.json
        ├── next-env.d.ts
        ├── .eslintrc.json
        ├── app/
        │   ├── globals.css
        │   ├── layout.tsx
        │   ├── page.tsx
        │   ├── login/
        │   │   └── page.tsx
        │   ├── signup/
        │   │   └── page.tsx
        │   ├── dashboard/
        │   │   └── page.tsx
        │   ├── auth/
        │   │   └── callback/
        │   │       └── google/
        │   │           └── page.tsx
        │   └── api/
        │       └── auth/
        │           ├── login/
        │           │   └── route.ts
        │           ├── signup/
        │           │   └── route.ts
        │           ├── logout/
        │           │   └── route.ts
        │           ├── refresh/
        │           │   └── route.ts
        │           ├── me/
        │           │   └── route.ts
        │           ├── google/
        │           │   └── route.ts
        │           ├── google-callback/
        │           │   └── route.ts
        │           └── projects/
        │               └── route.ts
        ├── components/
        │   └── ui/
        │       ├── button.tsx
        │       ├── card.tsx
        │       ├── form.tsx
        │       ├── input.tsx
        │       ├── label.tsx
        │       └── sonner.tsx
        ├── lib/
        │   ├── api.ts
        │   ├── auth.ts
        │   └── utils.ts
        └── middleware.ts
```

## 3.2 Database schema (ERD in text)

**users**

- id: uuid PK default uuidv7()
- email: citext UNIQUE NOT NULL
- email_verified_at: timestamptz NULL
- password_hash: text NULL
- full_name: text NULL
- avatar_url: text NULL
- google_sub: text UNIQUE NULL (partial unique where not null)
- last_login_at: timestamptz NULL
- is_active: boolean NOT NULL DEFAULT true
- created_at: timestamptz NOT NULL DEFAULT now()
- updated_at: timestamptz NOT NULL DEFAULT now()
- deleted_at: timestamptz NULL

**projects**

- id: uuid PK default uuidv7()
- slug: text UNIQUE NOT NULL
- name: text NOT NULL
- description: text NULL
- owner_user_id: uuid FK users.id NOT NULL
- settings: jsonb NOT NULL DEFAULT '{}'
- created_at, updated_at, deleted_at as above

**project_members**

- id: uuid PK default uuidv7()
- project_id: uuid FK projects.id NOT NULL
- user_id: uuid FK users.id NOT NULL
- role: text NOT NULL CHECK (OWNER|ADMIN|MEMBER)
- invited_by_user_id: uuid FK users.id NULL
- joined_at: timestamptz NOT NULL DEFAULT now()
- created_at, updated_at NOT NULL (no soft delete on members)
- UNIQUE (project_id, user_id)

**agents**

- id: uuid PK default uuidv7()
- project_id: uuid FK projects.id NOT NULL
- slug: text NOT NULL
- name: text NOT NULL
- description: text NULL
- agent_type: text NOT NULL DEFAULT 'custom'
- default_mode: text NOT NULL DEFAULT 'shadow' CHECK (enforce|shadow|audit)
- metadata: jsonb NOT NULL DEFAULT '{}'
- is_active: boolean NOT NULL DEFAULT true
- created_by_user_id: uuid FK users.id NOT NULL
- created_at, updated_at, deleted_at
- UNIQUE (project_id, slug)

**policies**

- id: uuid PK default uuidv7()
- project_id: uuid FK projects.id NOT NULL
- slug: text NOT NULL
- name: text NOT NULL
- description: text NULL
- pack: text NOT NULL DEFAULT 'custom'
- version: integer NOT NULL DEFAULT 1
- rules: jsonb NOT NULL DEFAULT '[]'
- is_active: boolean NOT NULL DEFAULT true
- created_by_user_id: uuid FK users.id NOT NULL
- created_at, updated_at, deleted_at
- UNIQUE (project_id, slug, version)

**api_keys**

- id: uuid PK default uuidv7()
- project_id: uuid FK projects.id NOT NULL
- name: text NOT NULL
- key_prefix: text NOT NULL
- key_hash: text NOT NULL
- scopes: text[] NOT NULL DEFAULT '{govern:write}'
- last_used_at: timestamptz NULL
- expires_at: timestamptz NULL
- created_by_user_id: uuid FK users.id NOT NULL
- revoked_at: timestamptz NULL
- created_at, updated_at (no soft delete)

**audit_events**

- id: uuid PK default uuidv7()
- actor_user_id: uuid FK users.id NULL
- project_id: uuid FK projects.id NULL
- event_type: text NOT NULL
- target_type: text NULL
- target_id: uuid NULL
- metadata: jsonb NOT NULL DEFAULT '{}'
- ip_address: inet NULL
- user_agent: text NULL
- created_at: timestamptz NOT NULL DEFAULT now()

**Relationships (high level)**

- users 1—* projects (as owner_user_id)
- projects 1—* project_members *—1 users
- projects 1—* agents, policies, api_keys
- users audit_events as actor; projects audit_events as scope

## 3.3 API routes (exhaustive list)

**Public**

| Method | Path | Auth |
|--------|------|------|
| GET | /healthz | none |
| GET | /readyz | none |
| POST | /api/v1/auth/signup | none |
| POST | /api/v1/auth/login | none |
| POST | /api/v1/auth/refresh | refresh token body |
| POST | /api/v1/auth/logout | Bearer JWT |
| GET | /api/v1/auth/google/authorize | none |
| POST | /api/v1/auth/google/callback | none |
| GET | /api/v1/auth/me | Bearer JWT |

**Users**

| Method | Path | Auth |
|--------|------|------|
| PATCH | /api/v1/users/me | Bearer JWT |
| POST | /api/v1/users/me/password | Bearer JWT |

**Projects**

| Method | Path | Auth + role |
|--------|------|-------------|
| GET | /api/v1/projects | JWT |
| POST | /api/v1/projects | JWT |
| GET | /api/v1/projects/{project_id} | JWT + member |
| PATCH | /api/v1/projects/{project_id} | JWT + ADMIN or OWNER |
| DELETE | /api/v1/projects/{project_id} | JWT + OWNER only |

**Members**

| Method | Path | Auth + role |
|--------|------|-------------|
| GET | /api/v1/projects/{project_id}/members | JWT + member |
| POST | /api/v1/projects/{project_id}/members | JWT + ADMIN or OWNER |
| PATCH | /api/v1/projects/{project_id}/members/{member_id} | JWT + OWNER (ADMIN: MEMBER→ADMIN only) |
| DELETE | /api/v1/projects/{project_id}/members/{member_id} | JWT + ADMIN or OWNER (rules: cannot remove OWNER; OWNER cannot remove self) |

**Agents**

| Method | Path | Auth + role |
|--------|------|-------------|
| GET | /api/v1/projects/{project_id}/agents | JWT + member |
| POST | /api/v1/projects/{project_id}/agents | JWT + ADMIN or OWNER |
| GET | /api/v1/projects/{project_id}/agents/{agent_id} | JWT + member |
| PATCH | /api/v1/projects/{project_id}/agents/{agent_id} | JWT + ADMIN or OWNER |
| DELETE | /api/v1/projects/{project_id}/agents/{agent_id} | JWT + ADMIN or OWNER |

**Policies**

| Method | Path | Auth + role |
|--------|------|-------------|
| GET | /api/v1/projects/{project_id}/policies | JWT + member |
| POST | /api/v1/projects/{project_id}/policies | JWT + ADMIN or OWNER |
| GET | /api/v1/projects/{project_id}/policies/{policy_id} | JWT + member |
| PATCH | /api/v1/projects/{project_id}/policies/{policy_id} | JWT + ADMIN or OWNER (new version row) |
| DELETE | /api/v1/projects/{project_id}/policies/{policy_id} | JWT + ADMIN or OWNER |

**API keys**

| Method | Path | Auth + role |
|--------|------|-------------|
| GET | /api/v1/projects/{project_id}/api-keys | JWT + member |
| POST | /api/v1/projects/{project_id}/api-keys | JWT + ADMIN or OWNER |
| DELETE | /api/v1/projects/{project_id}/api-keys/{key_id} | JWT + ADMIN or OWNER |

## 3.4 Implementation order (strict)

1. pyproject.toml + uv sync → Python deps installed
2. docker-compose.yml → Postgres 18 + Redis running
3. .env.example + src/axiom/config.py → settings load
4. src/axiom/db.py → async engine works, can `select 1`
5. src/axiom/models/*.py → all 7 models declared
6. alembic init + env.py async → alembic upgrade head creates tables
7. src/axiom/core/security.py → bcrypt + JWT tested
8. src/axiom/schemas/*.py → all Pydantic schemas
9. src/axiom/services/auth.py → signup + login + JWT issuance
10. src/axiom/services/google_oauth.py → authorization URL + token exchange
11. src/axiom/deps.py → get_db, get_current_user dependencies
12. src/axiom/routers/auth.py → /auth endpoints
13. src/axiom/routers/health.py → /healthz + /readyz
14. src/axiom/services/*.py (projects, agents, policies, api_keys) → business logic
15. src/axiom/routers/*.py (projects, agents, policies, api_keys, users, members) → endpoints
16. src/axiom/main.py → wire everything, middleware, CORS
17. tests/conftest.py → async test fixtures
18. tests/test_*.py → every endpoint has at least 1 happy-path + 1 auth-failure test
19. Frontend: scaffold Next.js 14 + Tailwind + shadcn
20. Frontend: login + signup + Google OAuth callback pages (minimal, not styled beyond functional)
21. Frontend: placeholder /dashboard page (Phase 3 will flesh it out)
22. `./axiom` CLI + `scripts/lib/axiom-*.sh` for dev orchestration (Phase 2.4; replaces legacy **`dev.sh`** / **`stop-dev.sh`** under **`scripts/`**)
23. docs/architecture.md + docs/decisions.md
24. Final verification: full stack up, signup flow works end-to-end via browser

## 3.5 Test gates

After step 6: `alembic upgrade head` must succeed cleanly
After step 12: `uv run pytest tests/test_auth.py -x -v` must pass 100% (auth tests split across files; full auth coverage in test_auth_*)
After step 18: `uv run pytest -x -v` must pass 100%
After step 20: `npm run build` must exit 0
After step 24: manual E2E — signup with Google works, signup with email works, both create valid JWT

## 3.6 Known risks

1. **OAuth state / CSRF** — Risk: forged callbacks. Mitigation: random `state` stored in Redis with TTL; callback must present valid state before token exchange.
2. **Refresh token theft** — Risk: long-lived tokens. Mitigation: store refresh `jti` in Redis with expiry; rotation on refresh optional Phase 2; revoke on logout.
3. **Race on project slug** — Risk: duplicate slug under concurrency. Mitigation: unique constraint + service maps IntegrityError to 409 Conflict.
4. **Login timing side channels** — Risk: user enumeration via bcrypt timing. Mitigation: always run bcrypt verify against a dummy hash when user missing.
5. **Cookie vs Bearer in tests** — Risk: drift between browser and API clients. Mitigation: tests use Bearer; Next BFF uses cookies only on browser paths.
6. **Mypy + FastAPI Depends** — Risk: noisy typing. Mitigation: typed `Annotated` aliases and explicit return types on deps.

## Completion report

- Commits: `feat(phase-1): foundation — auth, data model, scaffolding` on `main` (run `git log -1 --oneline` for the current hash)
- Tests: **32** passing, 0 failing (`uv run pytest -x -v`); coverage percentage not enforced in Phase 1
- Migration revisions: **d16ea780bf45** (`phase_1_foundation`)
- Endpoints: **34** FastAPI route handlers under `/healthz`, `/readyz`, and `/api/v1/*`
- Lines of code: backend **~3085** (`apps/backend/src/axiom/**/*.py`); frontend **~1307** (`apps/frontend` `*.ts`/`*.tsx`, excluding `node_modules` / `.next`)
- Time taken: multi-session implementation + verification gates (see section 7 in parent Phase 1 spec)

## What Phase 2 starts with

Ready-to-extend foundations:

- User/Project/Agent/Policy data models in place
- Authentication working (Google + email)
- API scaffolding with auto-docs
- Dev loop (`./axiom dev`) functional
- Zero technical debt, clean baselines

## What Phase 2 adds

- The `/v1/govern` endpoint (public, API-key-authenticated)
- The `executions` + `receipts` + `merkle_nodes` tables (new Alembic migration)
- 6-stage pipeline: Intent → Strategy → Authority → Dispatch → Evidence → Receipt
- Crypto layer: Ed25519 (PyNaCl) + ML-DSA-65 (via python-ml-dsa) + AES-256-GCM evidence vault
- RFC 6962 Merkle tree implementation
- Explanation engine embedded in Stage 3
- 20+ compliance framework policy packs seeded (EU AI Act, GDPR, HIPAA, etc.)
- 4 verdicts: APPROVE / MODIFY / ESCALATE / DENY
- Shadow / Enforce / Audit execution modes
- Prompt injection detection (17 signatures minimum)
