# Security audit (production readiness — Section F)

Formal pass over BFF routes, FastAPI handlers, and auth paths. Date aligned with audit closure workstream.

## BFF (Next.js Route Handlers)

| Item | Result | Notes |
|------|--------|--------|
| Session validation on authenticated routes | ✅ | Governance, projects, `me`, and verify routes read `access_token` from httpOnly cookie and return 401 when missing. Public receipt route proxies without session when using `share_token` by design. |
| Input validation | ✅ | BFF forwards query/body to FastAPI; Pydantic validates on the backend. |
| Error responses leak internals | ✅ | BFF passes through JSON error envelopes from the API; backend avoids stack traces in responses (see below). |
| Rate limiting on auth | ✅ | Signup/login/refresh/OAuth callback use SlowAPI limits on **backend** `/api/v1/auth/*` (e.g. signup 10/min, login 5/min). |
| CSRF on POST/DELETE | ✅ | Mutations use `credentials: "include"` with `SameSite` cookies (`lax` by default, configurable). No CSRF token: reliance on same-site cookies + no simple cross-origin form posts to BFF. |

## Backend (FastAPI)

| Item | Result | Notes |
|------|--------|--------|
| SQL injection | ✅ | Data access uses SQLAlchemy 2.0 async ORM / Core with bound parameters; no ad-hoc string SQL in governance paths reviewed. |
| Authorization (cross-user / cross-project) | ✅ | Governance and chains resolve identity via `resolve_api_key_or_current_user` / `require_api_key`; receipt and chain access checks `receipt.project_id == api_ctx.project_id`. JWT path requires `project_id` when the user has multiple projects. |
| API key scope | ✅ | SDK keys verified with scopes; governance dashboard paths expect `govern:write` (or JWT session surrogate). Admin-only routers are separate from governance API keys. |
| JWT expiry | ✅ | `decode_token` / `get_current_user` reject invalid or wrong-type tokens; expired JWTs fail verification. |
| Password hashing | ✅ | Auth service uses bcrypt via passlib-style configuration in codebase (see `axiom.services.auth`). |

## Error handling

- Unhandled exceptions return a generic `internal_error` message without exception text (`axiom.main` exception handler).
- `HTTPException` uses FastAPI’s handler without attaching tracebacks to clients.

## Items not changed in this pass

- OAuth and login flows were explicitly out of scope for edits.
- Dedicated CSRF tokens were not added; SameSite + same-origin BFF pattern is the current mitigation.
