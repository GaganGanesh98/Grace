# Phase 2.4 — `./axiom` CLI (single-command dev orchestration)

**Target tag:** `v0.2.4-devloop`
**Previous tag:** `v0.2.3-auth-fix`
**Scope:** `scripts/`, `docs/`, repo-root `./axiom`, `.gitignore`, `README.md`, `docs/decisions.md` (ADR-025). No application source or dependency manifest changes.

## Charter

- One entrypoint: **`./axiom`** with subcommands **dev**, **stop**, **fresh**, **status**, **logs**, **test**, **help**.
- Pure bash; **`set -euo pipefail`**; paths resolved from **`${BASH_SOURCE[0]}`** only (CWD-independent).
- **No `sudo docker`**; docker group membership is **mandatory** (preflight + `docs/dev-setup.md`).
- Host ports aligned with **`docker-compose.yml`**: Postgres **5433**, Redis **6380**, backend **8000**, frontend **3000**.
- **`./axiom stop`** → `docker compose stop` (volumes preserved). **`./axiom fresh`** → `docker compose down -v` then full bring-up.

## Verification (implementation)

- `shellcheck` clean on `axiom` and `scripts/lib/*.sh`.
- `./axiom help` and `./axiom` from repo root, `apps/backend`, and `/tmp` with absolute path.
- `./axiom test` runs CI-equivalent gates; `./axiom test --fast` runs pytest + vitest only.
- `grep` for removed script paths is empty (see Phase 2.4 checklist in main PR).

## Completion report

*(Append date, verifier, and short summary after merge/tag.)*
