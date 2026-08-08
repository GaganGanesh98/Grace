# Authentication setup (Grace)

Email/password and Google OAuth for local development and production.

## Backend environment files

Pydantic Settings loads these files **from the repository root**, in order (later files **override** earlier ones for duplicate keys):

1. `.env` (repo root, optional)
2. `.env.dev` (repo root, optional)
3. `apps/backend/.env` (optional, **gitignored** — common place for real dev secrets)

Missing optional files are ignored. **You do not need** all three; most developers use **`apps/backend/.env`** only (copy variable names from repo-root `.env.example`).

Required variables (non-OAuth): see `.env.example` — `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY`, etc.

### Google OAuth variables

| Variable | Required for Google sign-in | Notes |
|----------|------------------------------|--------|
| `GOOGLE_CLIENT_ID` | Yes | OAuth 2.0 Client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Yes | OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Strongly recommended | Must **exactly** match an **Authorized redirect URI** in Google Cloud Console |

**Local development — correct redirect URI**

Use this exact value (also the default in `config.py` if unset):

```text
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback/google
```

**Wrong (do not use for this stack):** redirecting to the FastAPI host, e.g. `http://localhost:8000/auth/google/callback`. Google must return the browser to the **Next.js** app, which completes the flow and calls the backend.

After changing `.env` files, restart the backend. Clear any cached settings in long-running shells (restart `uvicorn`).

## Google Cloud Console

1. Open [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → your OAuth 2.0 Client ID.
2. Under **Authorized redirect URIs**, add **exactly**:

   `http://localhost:3000/auth/callback/google`

3. Save. If this URI is missing, Google returns **`redirect_uri_mismatch`** after you pick an account.

**Smoke test:** Before relying on Google login locally, confirm this URI appears in the list (or add it). The codebase cannot verify Console configuration for you.

## Frontend

Copy `apps/frontend/.env.example` → `apps/frontend/.env.local` and set:

```text
API_URL=http://localhost:8000
```

The browser talks to Next.js route handlers (`/api/auth/...`), which proxy to the FastAPI backend.

## Running locally

From the repo root:

```bash
./axiom dev
```

- Backend: `http://localhost:8000` (or `http://127.0.0.1:8000`)
- Frontend: `http://localhost:3000`

`./axiom dev` starts uvicorn with **current working directory** `apps/backend`. Env **file paths** are still resolved from the **repo root** in `config.py`, so configuration is consistent regardless of CWD.

## Production notes

- Set OAuth variables via the deployment platform’s secret manager or environment injection (never commit secrets).
- `GOOGLE_REDIRECT_URI` must match the **public HTTPS** URL of your Next (or BFF) callback route, and that same URI must be authorized in Google Cloud Console.
- Use strong `SECRET_KEY`, `JWT_SECRET`, and `ENCRYPTION_KEY` (see `.env.example`).

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| HTTP **503** `service_unavailable` with message naming `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Variables empty or not loaded; confirm `apps/backend/.env` (or earlier file in the chain) and restart uvicorn. |
| **`redirect_uri_mismatch`** from Google | `GOOGLE_REDIRECT_URI` and Console **Authorized redirect URIs** must match **character for character** (scheme, host, port, path). |
| Email signup validation errors in the browser | Open DevTools → Network → confirm `POST /api/auth/signup` JSON includes `email`, `password`, optional `full_name`. |
| **401** / browser **"Invalid Google identity token"** after successful token exchange | Often **`at_hash`**: Google’s ID token includes `at_hash`, and **`python-jose`** validates it only when the backend passes the OAuth **`access_token`** from the same token response into verification. Ensure you are on a backend revision that does this (Phase 2.3+). Server logs may include event **`google_id_token_verify_failed`** with the library error string (no token/PII). |
| Browser shows **"Invalid or expired OAuth state"** while the network shows a **200** on callback | React 18 **Strict Mode** in dev can double-invoke `useEffect`; the first POST consumes single-use CSRF state. The callback page uses a **`useRef` single-fire guard** (`google-callback-inner.tsx`, **ADR-024**). Do not weaken server-side state validation. |
