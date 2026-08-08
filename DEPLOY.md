# AXIOM V2 deployment guide

This document covers environment variables and platform settings for production-style deployments (e.g. Railway, Vercel). Adjust hostnames to your real domains.

## Backend service (FastAPI)

### Required environment variables

| Variable | Example | Notes |
|----------|---------|--------|
| `GRACE_DATABASE_URL` (or `DATABASE_URL`) | `postgresql+asyncpg://…` | Async SQLAlchemy URL |
| `GRACE_REDIS_URL` (or `REDIS_URL`) | `redis://…` | Redis 7 |
| `GRACE_SECRET_KEY` (or `SECRET_KEY`) | 64 hex chars | App secret |
| `GRACE_JWT_SECRET` (or `JWT_SECRET`) | 32+ hex chars | JWT signing |
| `GRACE_ENCRYPTION_KEY` (or `ENCRYPTION_KEY`) | 32 hex chars | Field encryption |
| `GRACE_ENVIRONMENT` (or `ENVIRONMENT`) | `production` | Disables `/docs`, `/openapi.json` when `production` |
| `GRACE_FRONTEND_URL` (or `APP_URL`) | `https://axiom.dev` | Public web app origin |
| `GRACE_API_URL` (or `API_URL`) | `https://api.axiom.dev` | Public API base (self-reference, links) |
| `GRACE_CORS_ORIGINS` (or `BACKEND_CORS_ORIGINS`) | `["https://axiom.dev","https://www.axiom.dev"]` or comma-separated | Must include every browser origin that calls the API with credentials |
| `GRACE_GOOGLE_CLIENT_ID` / `GRACE_GOOGLE_CLIENT_SECRET` | From Google Cloud | If using Google sign-in |
| `GRACE_GOOGLE_REDIRECT_URI` (or `GOOGLE_REDIRECT_URI`) | `https://axiom.dev/auth/callback/google` | **Must exactly match** an **Authorized redirect URI** in [Google Cloud Console](https://console.cloud.google.com/apis/credentials) for the OAuth client |

### Governance keys (required in production)

| Variable | Example | Notes |
|----------|---------|--------|
| `GRACE_ED25519_PRIVATE_PEM` / `GRACE_ED25519_PUBLIC_PEM` | PEM | Receipt signing |
| `GRACE_ML_DSA_PRIVATE_B64` / `GRACE_ML_DSA_PUBLIC_B64` | base64 | Post-quantum co-signature |
| `GRACE_EVIDENCE_KEY_B64` | base64, 32 bytes | Encrypts receipt evidence. **Losing this makes historical evidence permanently undecryptable.** |
| `GRACE_VAULT_KEK_B64` | base64, 32 bytes | Wraps per-row credential keys. Unset derives it from the evidence key, which is fine for dev and not for production. Must not equal the evidence key — the app refuses to start if it does. |
| `GRACE_VAULT_KEK_PREVIOUS_B64` | comma-separated base64 | Retired KEKs, during a rotation only |

Read [docs/runbooks/key-rotation.md](docs/runbooks/key-rotation.md) before setting
these, especially the backup and key-loss section.

### Recommended (cookies / ops parity)

| Variable | Example | Notes |
|----------|---------|--------|
| `GRACE_COOKIE_SECURE` | `true` | Aligns documented backend settings with production expectations |
| `GRACE_COOKIE_SAMESITE` | `lax` or `none` | Use `none` only for cross-site cookie scenarios (requires HTTPS + `Secure`) |
| `GRACE_COOKIE_DOMAIN` | `.axiom.dev` | Optional; set if cookies must span subdomains |
| `GRACE_VERIFY_BASE_URL` | `https://api.axiom.dev` | Verify URLs if distinct from `API_URL` |

### Railway (backend)

- **Health check path:** `GET /healthz` (expect 200).
- Set all secrets via Railway variables; do not commit real values.
- Ensure the service listens on the port Railway injects (`PORT` is standard; confirm your process binds to it if you customize the entrypoint).

### Google OAuth (production)

1. In Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs.
2. **Authorized redirect URIs:** add the full HTTPS URL that your **Next.js** app exposes for the callback, e.g. `https://axiom.dev/auth/callback/google`. This must match `GRACE_GOOGLE_REDIRECT_URI` / backend `google_redirect_uri` and the route your frontend implements.
3. **Authorized JavaScript origins:** add your site origin(s), e.g. `https://axiom.dev`.

> **Variable naming.** Phase 8.2 renamed these to `GRACE_*`. The `AXIOM_*`
> spelling still resolves and `GRACE_*` wins when both are set; the API logs a
> warning at startup naming every `AXIOM_*` variable still in use. Plan to
> remove the old spelling from your deployment.

## Frontend service (Next.js) or Vercel

### Required / common

| Variable | Example | Notes |
|----------|---------|--------|
| `API_URL` | `https://api.axiom.dev` | Server-side BFF proxy to FastAPI (see `getApiUrl()`). **Not** `NEXT_PUBLIC_*` unless client bundles must call the API directly. |
| `GRACE_COOKIE_SECURE` | `true` | Production HTTPS |
| `GRACE_COOKIE_SAMESITE` | `lax` | Or `none` for cross-site |
| `GRACE_COOKIE_DOMAIN` | `.axiom.dev` | Optional shared domain for cookies |

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
