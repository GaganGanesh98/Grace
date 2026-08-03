# Phase 2.3 Plan — Auth end-to-end fix

**Target tag:** `v0.2.3-auth-fix`
**Recon:** Confirmed (see discovery table in prior chat).
**Human gate:** Mandatory browser smoke test **PASS** before commit/push/tag — no exceptions (AP-9.5).

**Dev scripts note:** A local shell wrapper at `~/AXIOM-V2/dev` (not in git) may source `.env.dev`. **This phase fixes only checked-in behavior:** the dev entrypoint (now **`./axiom dev`**; was **`dev.sh`** under **`scripts/`** before Phase 2.4), `apps/backend/src/axiom/config.py`, frontend auth, tests, and `docs/auth-setup.md`.

---

## 4.1 Root causes (from recon + clarifications)

### [Bug A] Signup form — Zod: `expected string, received undefined` (email / password)

- **Static analysis:** `signupBodySchema` in `apps/frontend/lib/schemas.ts` uses **`email`**, **`password`**, **`full_name` (optional)**. `apps/frontend/app/signup/page.tsx` uses the standard pattern **`{...register("email")}`**, **`{...register("password")}`**, **`{...register("full_name")}`** on the shared **`Input`** component — **no schema vs `register()` name mismatch**.
- **Plausible runtime cause:** `Input` wraps **`@base-ui/react/input`**, which renders **`Field.Control`** (`FieldControl`). That layer composes refs (`forwardedRef`, internal `inputRef`, **`validation.inputRef`**) and merges `onChange` / `onBlur` with Base UI validation hooks. **react-hook-form** relies on a ref and events reaching the **same** native `<input>` that holds the value. If composition order or duplicate `ref` keys in `useRenderElement` causes RHF’s ref not to attach to the live control, **`getValues()` / resolver input can omit `email` and `password`**, producing exactly Zod’s **“expected string, received undefined”** for those keys while `full_name` may still appear if `defaultValues` forces registration differently.
- **Plan:** Confirm in implementation by tracing **`register()` → `Input` → `InputPrimitive` → `FieldControl` → DOM`**. Fix by the smallest change that restores RHF↔native input wiring (e.g. **native `<input>`** for auth forms, **`Controller`**, or a thin **`forwardRef` input** that does not strip RHF’s ref — **not** weakening the schema with `.optional()` on required fields).

### [Bug B] Google OAuth env — empty `google_client_id` / secret at runtime

- **Root cause:** `Settings` used **`env_file=".env"`** relative to **process CWD** (typically `apps/backend` under `./axiom dev` / the old **`dev.sh`** in **`scripts/`**), not repo root; **`.env.dev` was never read by Pydantic** unless exported into the environment. Developers who only filled **`/.env.dev`** (or used a wrong file) see **`OAuthConfigurationError` → 503** despite “having secrets somewhere.”
- **Clarifications to implement:**
  1. **`get_settings()` / `Settings`:** Resolve **`REPO_ROOT`** from `config.py`’s file path and set **`env_file`** to load from repo root with **precedence in development:** **`.env` then `.env.dev`**, with **`.env.dev` overriding** (Pydantic Settings: pass a **tuple** of paths in order; **last file wins** for duplicate keys — verify with project’s `pydantic-settings` version). Use **`env_ignore_missing=True`** (or equivalent) so a missing `.env.dev` does not fail startup.
  2. **Dev entrypoint** (`./axiom dev` / legacy `dev.sh` in `scripts/`): `set -a; source ./.env.dev; set +a` when `./.env.dev` exists, then launch uvicorn — belt-and-suspenders with Settings `env_file`.
  3. **Do not commit** `.env.dev` or secrets.

### [Bug C] Google OAuth end-to-end + redirect URI

- **Backend** already exposes **`GET /api/v1/auth/google/authorize`** and **`POST /api/v1/auth/google/callback`**, with **state in Redis** and callback validation in `google_oauth.py`. Frontend BFF and **`/auth/callback/google`** page already match the **correct** redirect target for this stack.
- **Wrong developer config:** `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback` in **`.env.dev`** does **not** match the app (Google must redirect to the **Next** callback: **`http://localhost:3000/auth/callback/google`**). That mismatch causes **`redirect_uri_mismatch`** (or broken flow) after Bug B is fixed.
- **Plan:** Document and enforce alignment:
  - **`.env.example`**, **`docs/auth-setup.md`**, and implementation comments: the **only** authorized redirect URI for local dev in this architecture is **`http://localhost:3000/auth/callback/google`** (must match **Google Cloud Console**).
  - Developer action: **update `.env.dev`** to that URI; **Google Cloud Console** → OAuth client → **Authorized redirect URIs** must include the **exact** string.
- **503 copy:** When OAuth is misconfigured, error body must **name missing env vars** (never log or return `client_secret`).

---

## 4.2 Scope

| In scope | Out of scope (per phase charter) |
|----------|----------------------------------|
| Fix A: signup/login form value capture + validation | Password reset, email verification |
| Fix B: Settings `env_file` from repo root + precedence + dev entrypoint `.env.dev` source | Other OAuth providers |
| Fix C: redirect URI docs + verify full flow after A/B | SAML/SSO, governance engine / preflight code unless unavoidable |
| E2E tests (signup + Google OAuth happy + failure paths) | Schema migrations, V1 |
| **`docs/auth-setup.md`** (dev + prod + troubleshooting) | UI redesign |
| Clear errors for misconfiguration | — |
| **Mandatory human smoke test before commit** | Commit/tag without human PASS |

---

## 4.3 Implementation order

### Fix A — Signup (and login if same `Input`)

1. Trace `register()` → `components/ui/input.tsx` → Base UI `FieldControl` (already read in plan).
2. Apply minimal fix so RHF receives **`email`**, **`password`** (and **`full_name`** on signup) on submit.
3. Add a **small test** on the frontend if the repo already supports it (e.g. Vitest/Jest); if not, **backend contract + E2E** coverage is sufficient per gates.
4. **Contract / E2E:** `POST` signup payload shape **`{ email, password, full_name? }`** matches backend `SignupRequest`.

### Fix B — Settings + dev entrypoint (`./axiom dev`)

1. Add **`REPO_ROOT`** in `config.py` (e.g. `Path(__file__).resolve().parents[N]` — **verify `N`** so it points at repo root, not `apps/`).
2. Replace single `env_file=".env"` with **tuple** from `REPO_ROOT`: **(`.env`, `.env.dev`)**, **`env_ignore_missing=True`**, keep **`case_sensitive=False`**, **`extra="ignore"`**.
3. Optionally gate **`.env.dev` participation** on `ENVIRONMENT=development` if we want production images to never read `.env.dev` (even if absent); if gated, document behavior in `docs/auth-setup.md`.
4. Update the dev entrypoint (Phase 2.4: **`scripts/lib/axiom-dev.sh`**; Phase 2.3 era: **`dev.sh`** in **`scripts/`**): from repo root, if **`./.env.dev`** exists: `set -a; source ./.env.dev; set +a`; then start backend from `apps/backend` as today.
5. **Verify:** `cd /tmp && uv run python -c "…"` still loads Google vars when only files under repo root are populated (after cache clear or subprocess).

### Fix C — OAuth flow + errors + redirect

1. After B, **`build_authorize_url`** should see non-empty **`google_client_id`** / secret.
2. Ensure **`google_redirect_uri`** from env matches **`.env.example`** default **`http://localhost:3000/auth/callback/google`** unless deliberately overridden for another environment (document in `docs/auth-setup.md`).
3. Improve **`OAuthConfigurationError`** (and any 503 mapping) so **`details` / `message`** lists **which** of **`GOOGLE_CLIENT_ID`**, **`GOOGLE_CLIENT_SECRET`**, **`GOOGLE_REDIRECT_URI`** are missing or empty (no secret values).
4. **CSRF:** keep existing Redis state validation; add/adjust tests for **state mismatch → 400** (or mapped error code).
5. **Idempotency:** existing `ensure_google_user` — add/keep test: **same Google `sub` twice → one user**.

### Production vs development

6. **Development:** warn if Google vars missing; allow startup (email auth still usable).
7. **Production:** refuse startup if OAuth routes would be broken **only if** product decision is “OAuth required in prod” — otherwise document “email-only prod” explicitly. Align with existing patterns in `config.py` for other secrets.

### Tests (backend)

8. **Unit / schema:** signup schema or serializer accepts valid payload.
9. **`tests/e2e/test_auth_signup_flow.py`:** happy path register → tokens (use existing test client patterns / DB).
10. **`tests/e2e/test_google_oauth_flow.py`:** respx (or httpx mocking) for authorize URL + token exchange; **state mismatch**; **503 / clear message** when `GOOGLE_CLIENT_ID` empty (subprocess or `monkeypatch` env).
11. **Settings test:** `get_settings()` loads from **repo-root** files; **`.env.dev` overrides `.env`** for a controlled key (tmp dir or fixture files — avoid touching real secrets).

### Docs

12. **`docs/auth-setup.md`:** email + Google; **exact** local redirect URI **`http://localhost:3000/auth/callback/google`**; Google Console steps; **wrong** `http://localhost:8000/...` called out explicitly; prod notes; troubleshooting (503, `redirect_uri_mismatch`, CORS).

### Human smoke test (mandatory — Section 7 step 8)

13. Cursor runs gates **1–7** (lint, mypy, pytest, coverage, frontend build) first.
14. Post to chat **smoke checklist** with **http://localhost:3000** (`/signup`, `/login`, `/auth/callback/google`).
15. **Stop:** no `git commit` / **no tag** `v0.2.3-auth-fix` until developer replies **PASS** (screenshots optional but encouraged on FAIL).

### Finalize (only after PASS)

16. `git commit` with message template from phase charter.
17. `git tag -a v0.2.3-auth-fix …` and push per project convention.
18. Append **completion report** (date, verifier, what was verified) to **this file** below a `---` separator.

---

## 4.4 Risks + mitigations

| Risk | Mitigation |
|------|------------|
| Base UI + RHF edge case is subtle | Prefer minimal DOM-level fix; verify with Network payload + one E2E |
| `parents[N]` wrong for `REPO_ROOT` | Unit test or assertion that `REPO_ROOT / "README.md"` exists in dev |
| Google Console access | `docs/auth-setup.md` lists exact URI; developer registers it during smoke test |
| Human smoke test blocks merge | Acceptable — explicit goal of this phase (AP-9.5) |
| Phase 2 / 2.25 drift | Before commit: `git diff` against governance/preflight paths — **expected empty** |

---

## 4.5 Verification checklist (implementation phase)

- `pre-commit run --all-files`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src`
- `uv run pytest --cov=axiom --cov-branch --cov-fail-under=80 -v` (or project-standard command)
- Per-module gates if still in CI: `auth` / `google_oauth` coverage floors
- New: `uv run pytest tests/e2e/test_auth_signup_flow.py tests/e2e/test_google_oauth_flow.py -v`
- Settings: `get_settings()` shows Google configured when repo-root `.env` / `.env.dev` populated **without** relying on CWD
- Frontend: `npm run build` (and `tsc` / lint if scripted)
- `git diff v0.2.25-preflight..HEAD --stat --` governance paths → **empty**

---

## 4.6 Smoke test script (for chat — fill nothing else)

1. Stop running dev processes.
2. Run **`./axiom dev`** from repo root (or your local wrapper after aligning env).
3. Open **http://localhost:3000/signup**.
4. Sign up with a **new** email + password → expect **authenticated** landing (dashboard or equivalent).
5. DevTools → Network → confirm signup request JSON has **`email`**, **`password`**, optional **`full_name`**.
6. Log out.
7. **http://localhost:3000/login** → same email/password → authenticated.
8. Log out.
9. **Google Cloud Console:** In APIs & Services → Credentials → your OAuth client → **Authorized redirect URIs**, confirm **`http://localhost:3000/auth/callback/google`** is listed (add it if not). Otherwise Google returns **`redirect_uri_mismatch`**.
10. **Continue with Google** → Google consent → return to **`http://localhost:3000/auth/callback/google?...`** → authenticated.
11. Hard refresh → still authenticated.
12. Reply **PASS** or **FAIL** (+ what broke).

---

## Completion report

*(Leave blank until developer reports smoke test PASS; then append date, name, and short verification summary.)*
