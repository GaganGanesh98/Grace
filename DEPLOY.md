# AXIOM V2 deployment guide

This document covers environment variables and platform settings for production-style deployments (e.g. Railway, Vercel). Adjust hostnames to your real domains.

## Backend service (FastAPI)

### Required environment variables

| Variable | Example | Notes |
|----------|---------|--------|
| `DATABASE_URL` | `postgresql+asyncpg://…` | Async SQLAlchemy URL |
| `REDIS_URL` | `redis://…` | Redis 7 |
| `SECRET_KEY` | 64 hex chars | App secret |
| `JWT_SECRET` | 32+ hex chars | JWT signing |
| `ENCRYPTION_KEY` | 32 hex chars | Field encryption |
| `ENVIRONMENT` | `production` | Disables `/docs`, `/openapi.json` when `production` |
| `APP_URL` or `AXIOM_FRONTEND_URL` | `https://axiom.dev` | Public web app origin |
| `API_URL` or `AXIOM_API_URL` | `https://api.axiom.dev` | Public API base (self-reference, links) |
| `BACKEND_CORS_ORIGINS` or `AXIOM_CORS_ORIGINS` | `["https://axiom.dev","https://www.axiom.dev"]` or comma-separated | Must include every browser origin that calls the API with credentials |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | From Google Cloud | If using Google sign-in |
| `GOOGLE_REDIRECT_URI` | `https://axiom.dev/auth/callback/google` | **Must exactly match** an **Authorized redirect URI** in [Google Cloud Console](https://console.cloud.google.com/apis/credentials) for the OAuth client |

### Recommended (cookies / ops parity)

| Variable | Example | Notes |
|----------|---------|--------|
| `AXIOM_COOKIE_SECURE` | `true` | Aligns documented backend settings with production expectations |
| `AXIOM_COOKIE_SAMESITE` | `lax` or `none` | Use `none` only for cross-site cookie scenarios (requires HTTPS + `Secure`) |
| `AXIOM_COOKIE_DOMAIN` | `.axiom.dev` | Optional; set if cookies must span subdomains |
| `AXIOM_VERIFY_BASE_URL` | `https://api.axiom.dev` | Verify URLs if distinct from `API_URL` |

### Railway (backend)

- **Health check path:** `GET /healthz` (expect 200).
- Set all secrets via Railway variables; do not commit real values.
- Ensure the service listens on the port Railway injects (`PORT` is standard; confirm your process binds to it if you customize the entrypoint).

### Google OAuth (production)

1. In Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs.
2. **Authorized redirect URIs:** add the full HTTPS URL that your **Next.js** app exposes for the callback, e.g. `https://axiom.dev/auth/callback/google`. This must match `GOOGLE_REDIRECT_URI` / backend `google_redirect_uri` and the route your frontend implements.
3. **Authorized JavaScript origins:** add your site origin(s), e.g. `https://axiom.dev`.

## Frontend service (Next.js) or Vercel

### Required / common

| Variable | Example | Notes |
|----------|---------|--------|
| `API_URL` | `https://api.axiom.dev` | Server-side BFF proxy to FastAPI (see `getApiUrl()`). **Not** `NEXT_PUBLIC_*` unless client bundles must call the API directly. |
| `AXIOM_COOKIE_SECURE` | `true` | Production HTTPS |
| `AXIOM_COOKIE_SAMESITE` | `lax` | Or `none` for cross-site |
| `AXIOM_COOKIE_DOMAIN` | `.axiom.dev` | Optional shared domain for cookies |

### Domain setup (typical)

- Point `axiom.dev` (or `www`) to the Next.js host (Vercel/Railway static/Node).
- Point `api.axiom.dev` to the FastAPI backend.
- TLS certificates on both; browsers require `Secure` cookies for `SameSite=None`.

## Smoke tests (Playwright)

From `apps/frontend`, with dev stack up or `reuseExistingServer`, run `npm run test:e2e`. Health check uses `API_URL` or defaults to `http://127.0.0.1:8000`.

## See also

- `apps/backend/.env.example` — full backend variable list.
- `apps/frontend/.env.example` — frontend / BFF variables.
- `docs/auth-setup.md` — OAuth troubleshooting.
